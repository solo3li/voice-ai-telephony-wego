/**
 * Knowledge Base (RAG) JavaScript
 * Handles document upload, status polling, embedding progress, and deletion.
 */

let fileInput = null;
let uploadLabel = null;
let btnUpload = null;
let uploadStatus = null;
let docsTbody = null;

function handleFileSelect(e) {
  if (!fileInput || !uploadLabel || !btnUpload) return;
  if (fileInput.files && fileInput.files.length > 0) {
    uploadLabel.innerText = fileInput.files[0].name;
    btnUpload.disabled = false;
  } else {
    uploadLabel.innerText = 'اختر ملفاً (PDF/DOCX/TXT)';
    btnUpload.disabled = true;
  }
}

async function loadDocuments() {
  if (!docsTbody) return;
  try {
    const res = await fetch('/api/knowledge/documents/');
    const data = await res.json();
    if (data.status === 'success') {
      renderDocuments(data.documents);
      if (data.documents && data.documents.some(d => d.status === 'pending')) {
        setTimeout(loadDocuments, 3000);
      }
    }
  } catch (err) {
    console.error('Error fetching documents:', err);
  }
}

function renderDocuments(docs) {
  if (!docsTbody) return;
  if (!docs || docs.length === 0) {
    docsTbody.innerHTML = `
      <tr>
        <td colspan="5" class="text-center py-6 text-[#8C827A]">
          لا توجد مستندات مرفوعة بعد. ارفع أول ملف لبدء الإجابة منه!
        </td>
      </tr>
    `;
    return;
  }

  docsTbody.innerHTML = docs.map(d => {
    let statusBadge = '';
    if (d.status === 'pending') {
      statusBadge = `<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-100 text-amber-800 border border-amber-200 animate-pulse">⏳ قيد الفهرسة</span>`;
    } else if (d.status === 'failed') {
      statusBadge = `<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-rose-100 text-rose-800 border border-rose-200" title="${escapeHtml(d.error_message || '')}">❌ فشل</span>`;
    } else {
      statusBadge = `<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-100 text-emerald-800 border border-emerald-200">✅ جاهز</span>`;
    }

    return `
    <tr class="hover:bg-[#F5EFE6]/60 transition">
      <td class="py-3 px-3 font-medium text-[#1C1917] font-bold flex items-center gap-2">
        <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4 text-[#6E645D] flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
        ${escapeHtml(d.title)}
      </td>
      <td class="py-3 px-3 text-[#6E645D] uppercase">${escapeHtml(d.file_type)}</td>
      <td class="py-3 px-3">
        <div class="flex items-center gap-2">
          <span class="text-[#680E23] font-semibold">${d.chunks_count} مقطع</span>
          ${statusBadge}
        </div>
      </td>
      <td class="py-3 px-3 text-[#6E645D] font-mono text-[11px]">${escapeHtml(d.created_at)}</td>
      <td class="py-3 px-3 text-center">
        <button onclick="deleteDocument(${d.id})" class="text-rose-600 hover:text-rose-800 p-1.5 rounded-lg hover:bg-rose-50 transition" title="حذف المستند">
          <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
          </svg>
        </button>
      </td>
    </tr>
  `}).join('');
}

async function uploadDocument(e) {
  e.preventDefault();
  if (!fileInput || !fileInput.files || fileInput.files.length === 0) return;

  const file = fileInput.files[0];
  const formData = new FormData();
  formData.append('file', file);

  btnUpload.disabled = true;
  btnUpload.innerHTML = `
    <svg class="animate-spin -ml-1 mr-2 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
      <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
      <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
    </svg>
    جاري المعالجة والتضمين...
  `;

  if (uploadStatus) {
    uploadStatus.className = 'mt-4 p-3 rounded-xl text-xs bg-[#FAF0F2] border border-[#EAE3D9] text-[#680E23] flex items-center gap-2';
    uploadStatus.innerHTML = 'جاري استخراج النصوص وتوليد التضمينات الدلالية عبر Gemini...';
    uploadStatus.classList.remove('hidden');
  }

  try {
    const res = await fetch('/api/knowledge/documents/upload/', {
      method: 'POST',
      headers: {
        'X-CSRFToken': getCookie('csrftoken'),
      },
      body: formData,
    });
    const result = await res.json();
    if (result.status === 'success') {
      if (uploadStatus) {
        uploadStatus.className = 'mt-4 p-3 rounded-xl text-xs bg-emerald-50 border border-emerald-200 text-emerald-800 flex items-center gap-2';
        uploadStatus.innerHTML = '✅ ' + escapeHtml(result.message);
      }
      fileInput.value = '';
      if (uploadLabel) uploadLabel.innerText = 'اختر ملفاً (PDF/DOCX/TXT)';
      showToast('تم رفع المستند وبدء الفهرسة بنجاح', 'success');
      await loadDocuments();
    } else {
      if (uploadStatus) {
        uploadStatus.className = 'mt-4 p-3 rounded-xl text-xs bg-rose-50 border border-rose-200 text-rose-800 flex items-center gap-2';
        uploadStatus.innerHTML = '❌ فشل الرفع: ' + escapeHtml(result.message || 'خطأ غير معروف');
      }
      showToast(result.message || 'فشل الرفع', 'error');
    }
  } catch (err) {
    if (uploadStatus) {
      uploadStatus.className = 'mt-4 p-3 rounded-xl text-xs bg-rose-50 border border-rose-200 text-rose-800 flex items-center gap-2';
      uploadStatus.innerHTML = '❌ خطأ في الاتصال بالخادم أثناء الرفع.';
    }
    showToast('خطأ في الاتصال بالخادم أثناء الرفع.', 'error');
  } finally {
    btnUpload.disabled = false;
    btnUpload.innerHTML = '<span>رفع ومعالجة</span>';
  }
}

async function deleteDocument(docId) {
  if (!confirm('هل أنت متأكد من رغبتك في حذف هذا المستند وحذف جميع مقاطعه الدلالية؟')) return;
  try {
    const res = await fetch(`/api/knowledge/documents/${docId}/delete/`, {
      method: 'POST',
      headers: {
        'X-CSRFToken': getCookie('csrftoken'),
      }
    });
    const result = await res.json();
    if (result.status === 'success') {
      showToast('تم حذف المستند بنجاح', 'success');
      await loadDocuments();
    } else {
      showToast('فشل الحذف: ' + (result.message || 'خطأ غير معروف'), 'error');
    }
  } catch (err) {
    showToast('حدث خطأ أثناء الاتصال بالخادم لحذف المستند.', 'error');
  }
}

document.addEventListener('DOMContentLoaded', () => {
  fileInput = document.getElementById('file-input');
  uploadLabel = document.getElementById('upload-file-label');
  btnUpload = document.getElementById('btn-upload');
  uploadStatus = document.getElementById('upload-status');
  docsTbody = document.getElementById('docs-tbody');

  loadDocuments();
});
