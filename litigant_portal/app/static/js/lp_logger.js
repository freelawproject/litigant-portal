;(function () {
  const { url, csrfToken } = document.currentScript.dataset
  window.lpLogger = function (options) {
    try {
      const body = new URLSearchParams({
        csrfmiddlewaretoken: csrfToken,
        options: JSON.stringify({
          ...options,
          type: options.type instanceof Error ? 'error' : options.type,
        }),
      })
      fetch(url, {
        method: 'POST',
        mode: 'same-origin',
        referrer: '',
        referrerPolicy: 'same-origin',
        body,
      }).catch(() => {})
    } catch {
      // Transport failures must not prevent local console output.
    }
    console.log(options)
  }
})()
