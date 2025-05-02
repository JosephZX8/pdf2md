<template>
  <div class="space-y-6">
    <!-- 上传区域 -->
    <div class="bg-white shadow rounded-lg p-6">
      <div class="space-y-4">
        <h2 class="text-lg font-medium text-gray-900">上传 PDF 文件</h2>
        <div 
          class="flex justify-center px-6 pt-5 pb-6 border-2 border-gray-300 border-dashed rounded-md"
          @dragover.prevent
          @drop.prevent="handleDrop"
        >
          <div class="space-y-1 text-center">
            <svg class="mx-auto h-12 w-12 text-gray-400" stroke="currentColor" fill="none" viewBox="0 0 48 48">
              <path d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28m0 0l4 4m4-24h8m-4-4v8m-12 4h.02" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
            <div class="flex text-sm text-gray-600">
              <label class="relative cursor-pointer bg-white rounded-md font-medium text-primary-600 hover:text-primary-500 focus-within:outline-none focus-within:ring-2 focus-within:ring-offset-2 focus-within:ring-primary-500">
                <span>上传文件</span>
                <input type="file" class="sr-only" accept=".pdf" @change="handleFileSelect">
              </label>
              <p class="pl-1">或将文件拖放到此处</p>
            </div>
            <p class="text-xs text-gray-500">PDF 文件，最大 10MB</p>
          </div>
        </div>
      </div>
    </div>

    <!-- 预览区域 -->
    <div v-if="pdfStore.content" class="bg-white shadow rounded-lg p-6">
      <div class="flex justify-between items-center mb-4">
        <h2 class="text-lg font-medium text-gray-900">预览</h2>
        <button 
          @click="downloadMarkdown" 
          class="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-primary-600 hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500"
        >
          下载 Markdown
        </button>
      </div>
      <div class="prose max-w-none" v-html="renderedContent"></div>
    </div>

    <!-- 加载状态 -->
    <div v-if="pdfStore.loading" class="fixed inset-0 bg-gray-500 bg-opacity-75 flex items-center justify-center">
      <div class="bg-white rounded-lg p-6 max-w-sm w-full">
        <div class="text-center">
          <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600 mx-auto"></div>
          <p class="mt-4 text-sm text-gray-500">正在处理 PDF...</p>
        </div>
      </div>
    </div>

    <!-- 错误提示 -->
    <div v-if="pdfStore.error" class="bg-red-50 border-l-4 border-red-400 p-4">
      <div class="flex">
        <div class="flex-shrink-0">
          <svg class="h-5 w-5 text-red-400" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" />
          </svg>
        </div>
        <div class="ml-3">
          <p class="text-sm text-red-700">{{ pdfStore.error }}</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { usePdfStore } from '@/stores/pdf'

const pdfStore = usePdfStore()

// 配置 marked 以支持图片
marked.setOptions({
  renderer: new marked.Renderer(),
  gfm: true,
  breaks: true
})

const renderedContent = computed(() => {
  if (!pdfStore.content) return ''
  // 处理图片路径
  let processedContent = pdfStore.content
  pdfStore.images.forEach(image => {
    processedContent = processedContent.replace(
      new RegExp(`!\\[.*?\\]\\(${image}\\)`, 'g'),
      `![图片](/api/download/${image})`
    )
  })
  // 使用 DOMPurify 清理 HTML 内容
  return DOMPurify.sanitize(marked(processedContent))
})

const handleFileSelect = (event: Event) => {
  const input = event.target as HTMLInputElement
  if (input.files && input.files[0]) {
    handleFile(input.files[0])
  }
}

const handleDrop = (event: DragEvent) => {
  if (event.dataTransfer?.files && event.dataTransfer.files[0]) {
    handleFile(event.dataTransfer.files[0])
  }
}

const handleFile = (file: File) => {
  if (!file.type.includes('pdf')) {
    pdfStore.error = '请上传 PDF 文件'
    return
  }
  pdfStore.uploadPdf(file)
}

const downloadMarkdown = () => {
  const blob = new Blob([pdfStore.content], { type: 'text/markdown' })
  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = 'converted.md'
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  window.URL.revokeObjectURL(url)
}
</script>

<style>
.prose img {
  max-width: 100%;
  height: auto;
}
</style> 