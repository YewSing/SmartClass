import { Platform } from 'react-native'
import AsyncStorage from '@react-native-async-storage/async-storage'
import * as FileSystem from 'expo-file-system/legacy'
import * as Sharing from 'expo-sharing'

// Android: saves straight into a folder the lecturer picks once, remembered afterwards.
// iPhone: no shared folders to write to, so the share sheet ("Save to Files").
// The browser version is saveCsv.web.js.
const SAF = FileSystem.StorageAccessFramework
const FOLDER_KEY = 'csv_save_folder'

// Tree URI → readable path, e.g. ".../tree/primary%3ADownload%2FSmartClass" → "Download/SmartClass".
function folderLabel(uri) {
  const path = decodeURIComponent(uri).split(':').pop().replace(/^\/storage\/emulated\/0\//, '')
  return /[a-z]/i.test(path) ? path : 'your chosen folder'
}

export async function getSaveFolderLabel() {
  if (Platform.OS !== 'android') return null
  const uri = await AsyncStorage.getItem(FOLDER_KEY)
  return uri ? folderLabel(uri) : null
}

export async function forgetSaveFolder() {
  await AsyncStorage.removeItem(FOLDER_KEY)
}

// Returns the message to show, with the name Android really used.
async function writeInto(folderUri, csvText, filename) {
  // Android adds the .csv from the MIME type, and "name (1).csv" if the name is taken.
  const fileUri = await SAF.createFileAsync(folderUri, filename.replace(/\.csv$/i, ''), 'text/csv')
  await SAF.writeAsStringAsync(fileUri, csvText, { encoding: 'utf8' })
  return `Saved ${decodeURIComponent(fileUri).split('/').pop()} to ${folderLabel(folderUri)}`
}

async function saveOnAndroid(csvText, filename) {
  const remembered = await AsyncStorage.getItem(FOLDER_KEY)
  if (remembered) {
    try {
      return await writeInto(remembered, csvText, filename)
    } catch {
      // The folder was deleted or access was withdrawn: ask for a folder again.
      await forgetSaveFolder()
    }
  }

  const picked = await SAF.requestDirectoryPermissionsAsync(SAF.getUriForDirectoryInRoot('Download'))
  if (!picked.granted) throw new Error('No folder chosen, so the CSV was not saved.')
  const message = await writeInto(picked.directoryUri, csvText, filename)
  await AsyncStorage.setItem(FOLDER_KEY, picked.directoryUri)
  return message
}

async function shareOnIos(csvText, filename) {
  if (!(await Sharing.isAvailableAsync())) {
    throw new Error('Sharing is not available on this device.')
  }
  const uri = FileSystem.cacheDirectory + filename
  await FileSystem.writeAsStringAsync(uri, csvText, { encoding: 'utf8' })
  await Sharing.shareAsync(uri, { mimeType: 'text/csv', UTI: 'public.comma-separated-values-text', dialogTitle: 'Save CSV' })
  return null
}

// Returns a message to show the lecturer, or null when the share sheet already showed the outcome.
export async function saveCsv(csvText, filename) {
  return Platform.OS === 'android' ? saveOnAndroid(csvText, filename) : shareOnIos(csvText, filename)
}
