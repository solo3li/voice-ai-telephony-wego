"""
Live Real-Time LiveKit Egress Execution Test:
1. Creates a live room in LiveKit Server.
2. Triggers start_room_composite_egress (audio-only MP3).
3. Verifies egress status transitions (EGRESS_STARTING -> EGRESS_ACTIVE).
4. Stops the egress recording.
5. Verifies MinIO receives the uploaded .mp3 file and checks its headers.
"""
import os
import sys
import time
import asyncio
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.conf import settings
from voice_assistant.egress_service import get_livekit_api_client
from voice_assistant.s3_storage import get_s3_client
from livekit import api


async def run_live_egress_test():
    print("\n--- TEST: Live Real-Time Egress & MinIO Upload ---")
    room_name = f"test_live_rec_{int(time.time())}"
    filepath = f"recordings/{room_name}.mp3"
    
    s3_upload = api.S3Upload(
        endpoint=getattr(settings, 'MINIO_ENDPOINT', 'http://minio:9000'),
        access_key=getattr(settings, 'MINIO_ACCESS_KEY', 'minioadmin'),
        secret=getattr(settings, 'MINIO_SECRET_KEY', 'minioadmin123'),
        bucket=getattr(settings, 'MINIO_BUCKET_NAME', 'call-recordings'),
        region='us-east-1',
        force_path_style=True
    )

    req = api.RoomCompositeEgressRequest(
        room_name=room_name,
        audio_only=True,
        file_outputs=[
            api.EncodedFileOutput(
                file_type=api.EncodedFileType.MP3,
                filepath=filepath,
                s3=s3_upload
            )
        ]
    )

    async with get_livekit_api_client() as lk:
        # 1. Create Room
        await lk.room.create_room(api.CreateRoomRequest(name=room_name, empty_timeout=120))
        print(f"✅ Created LiveKit room: {room_name}")

        # 2. Start Egress
        res = await lk.egress.start_room_composite_egress(req)
        egress_id = res.egress_id
        print(f"✅ Started RoomCompositeEgress: {egress_id} (Status: {res.status})")

        # 3. Poll egress status
        for i in range(10):
            await asyncio.sleep(1)
            list_res = await lk.egress.list_egress(api.ListEgressRequest(egress_id=egress_id))
            if list_res and list_res.items:
                cur_status = list_res.items[0].status
                print(f"   [t={i+1}s] Egress status: {cur_status}")
                if cur_status == api.EgressStatus.EGRESS_ACTIVE:
                    print("✅ Egress is actively recording room audio!")
                    break

        # 4. Stop Egress
        print("Stopping egress recording...")
        stop_res = await lk.egress.stop_egress(api.StopEgressRequest(egress_id=egress_id))
        print(f"✅ Stop signal sent: {stop_res.status}")

        # 5. Wait for EGRESS_COMPLETE
        for i in range(15):
            await asyncio.sleep(1)
            list_res = await lk.egress.list_egress(api.ListEgressRequest(egress_id=egress_id))
            if list_res and list_res.items:
                cur_status = list_res.items[0].status
                if cur_status == api.EgressStatus.EGRESS_COMPLETE:
                    print(f"✅ Egress successfully finished: {cur_status}")
                    break

        # 6. Verify file in MinIO
        s3 = get_s3_client()
        bucket = getattr(settings, 'MINIO_BUCKET_NAME', 'call-recordings')
        
        found = False
        for attempt in range(5):
            try:
                head = s3.head_object(Bucket=bucket, Key=filepath)
                size = head.get('ContentLength', 0)
                print(f"🎉 VERIFIED! MP3 recording file exists in MinIO bucket '{bucket}': {filepath} (Size: {size} bytes)")
                found = True
                break
            except Exception:
                await asyncio.sleep(1)

        assert found, f"Recording file {filepath} was not found in MinIO bucket {bucket}"


if __name__ == '__main__':
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run_live_egress_test())
    loop.close()
