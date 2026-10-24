// File reading helpers. FileReader is used instead of Blob.text() so the
// code works identically in Electron, browsers, and jsdom-based tests.

export function readFileAsText(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      resolve(typeof reader.result === 'string' ? reader.result : '');
    };
    reader.onerror = () => {
      reject(reader.error ?? new Error('Failed to read the selected file.'));
    };
    reader.readAsText(file);
  });
}
