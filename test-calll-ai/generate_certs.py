import datetime
import ipaddress
from pathlib import Path
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

def generate_self_signed_cert():
    certs_dir = Path("traefik/certs")
    certs_dir.mkdir(parents=True, exist_ok=True)
    
    key_path = certs_dir / "local.key"
    cert_path = certs_dir / "local.crt"
    
    # Generate private key
    key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    
    # Subject and Issuer
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Local"),
        x509.NameAttribute(NameOID.LOCALITY_NAME, "Dev"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Dev"),
        x509.NameAttribute(NameOID.COMMON_NAME, "app.localhost"),
    ])
    
    # SAN (Subject Alternative Name)
    alt_names = [
        x509.DNSName("localhost"),
        x509.DNSName("*.localhost"),
        x509.DNSName("app.localhost"),
        x509.DNSName("centrifugo.localhost"),
        x509.DNSName("livekit.localhost"),
        x509.DNSName("169.58.32.179.nip.io"),
        x509.DNSName("*.169.58.32.179.nip.io"),
        x509.DNSName("app.169.58.32.179.nip.io"),
        x509.DNSName("centrifugo.169.58.32.179.nip.io"),
        x509.DNSName("livekit.169.58.32.179.nip.io"),
        x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
        x509.IPAddress(ipaddress.IPv4Address("169.58.32.179")),
    ]
    
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.now(datetime.timezone.utc))
        .not_valid_after(datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=3650))
        .add_extension(
            x509.SubjectAlternativeName(alt_names),
            critical=False,
        )
        .add_extension(
            x509.BasicConstraints(ca=True, path_length=None),
            critical=True,
        )
        .sign(key, hashes.SHA256())
    )
    
    # Write private key
    with open(key_path, "wb") as f:
        f.write(
            key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )
        
    # Write certificate
    with open(cert_path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))
        
    print(f"Generated successfully:\n  {key_path}\n  {cert_path}")

if __name__ == "__main__":
    generate_self_signed_cert()
