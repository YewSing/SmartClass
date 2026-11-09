// Browser: downloads the CSV through a temporary link (no file system or share sheet on web).
export async function saveCsv(csvText, filename) {
  const blob = new Blob([csvText], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 0)
  return `Downloaded ${filename}`
}

// The browser decides where downloads go, so there is no save folder to remember.
export async function getSaveFolderLabel() {
  return null
}

export async function forgetSaveFolder() {}
