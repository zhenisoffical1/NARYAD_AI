import imageCompression from 'browser-image-compression'

export interface PickedPhoto {
  id: string
  file: File
  url: string
}

/** Сжатие на клиенте: до 1600 px, JPEG 0.8, EXIF сохраняется (по нему сервер проверяет время съёмки). */
export async function compressPhoto(file: File): Promise<File> {
  const compressed = await imageCompression(file, {
    maxWidthOrHeight: 1600,
    initialQuality: 0.8,
    fileType: 'image/jpeg',
    preserveExif: true,
    useWebWorker: true,
  })
  return new File([compressed], file.name.replace(/\.\w+$/, '') + '.jpg', { type: 'image/jpeg' })
}
