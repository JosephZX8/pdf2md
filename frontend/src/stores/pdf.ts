import { defineStore } from 'pinia'
import { ref } from 'vue'
import axios from 'axios'

export const usePdfStore = defineStore('pdf', () => {
  const content = ref('')
  const loading = ref(false)
  const error = ref('')
  const images = ref<string[]>([])

  async function uploadPdf(file: File) {
    loading.value = true
    error.value = ''
    
    const formData = new FormData()
    formData.append('file', file)

    try {
      const response = await axios.post('/api/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      })

      if (response.data.success) {
        content.value = response.data.content
        images.value = response.data.images || []
      } else {
        error.value = response.data.error || '处理失败'
      }
    } catch (err) {
      error.value = err instanceof Error ? err.message : '上传失败'
    } finally {
      loading.value = false
    }
  }

  function clear() {
    content.value = ''
    loading.value = false
    error.value = ''
    images.value = []
  }

  return {
    content,
    loading,
    error,
    images,
    uploadPdf,
    clear
  }
}) 