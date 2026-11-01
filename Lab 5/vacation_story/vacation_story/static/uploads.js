/* Serial uploads keep each phone photo within the server's per-file limit. */
window.VacationUploads = {
  async uploadBatch(files, { submit, isCurrent, onProgress, onPhoto }) {
    const uploaded = [];
    const failures = [];
    for (let index = 0; index < files.length; index++) {
      if (!isCurrent()) return { uploaded, failures, cancelled: true };
      const file = files[index];
      onProgress({ index: index + 1, total: files.length, file });
      let photo;
      try { photo = await submit(file); }
      catch (error) {
        if (!isCurrent()) return { uploaded, failures, cancelled: true };
        failures.push({ file, message: error.message || 'Upload failed. Please try again.' });
        continue;
      }
      if (!isCurrent()) return { uploaded, failures, cancelled: true };
      uploaded.push(photo);
      onPhoto(photo);
    }
    return { uploaded, failures, cancelled: false };
  },
};
