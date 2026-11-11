// Enrolment photos on the phone (NFR-01): shrink right after the shot, delete when done.
import * as FileSystem from 'expo-file-system/legacy'
import { manipulateAsync, SaveFormat } from 'expo-image-manipulator'
import { shrinkAction } from './faceEnrolment'

// Deletes photo files from the app cache. Never throws: a file already gone is fine.
export async function deletePhotos(uris) {
  await Promise.all(uris.filter(Boolean).map(uri =>
    FileSystem.deleteAsync(uri, { idempotent: true }).catch(() => {})))
}

// A camera photo shrunk to PHOTO_MAX_SIDE as a JPEG; the full-size original is deleted at once
export async function shrinkPhoto(photo) {
  const action = shrinkAction(photo.width, photo.height)
  if (!action) return { uri: photo.uri }
  try {
    const small = await manipulateAsync(photo.uri, [action], { compress: 0.85, format: SaveFormat.JPEG })
    await deletePhotos([photo.uri])
    return { uri: small.uri }
  } catch {
    return { uri: photo.uri } // keep the original rather than lose the shot
  }
}
