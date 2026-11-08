import * as FileSystem from 'expo-file-system/legacy'
import * as Sharing from 'expo-sharing'

// Phone: writes CSV text to a temp file in the cache dir and opens the native share sheet.
// The browser version is saveCsv.web.js.
export async function saveCsv(csvText, filename) {
  if (!(await Sharing.isAvailableAsync())) {
    throw new Error('Sharing is not available on this device.')
  }
  const uri = FileSystem.cacheDirectory + filename
  await FileSystem.writeAsStringAsync(uri, csvText, { encoding: 'utf8' })
  await Sharing.shareAsync(uri, { mimeType: 'text/csv', dialogTitle: 'Save CSV' })
}
