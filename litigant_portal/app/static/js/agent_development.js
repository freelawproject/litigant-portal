// Keep the topic picker within the selected court, preserving blank discovery.
const agentDevelopmentForm = document.getElementById('agent-development-form')

if (agentDevelopmentForm) {
  const court = agentDevelopmentForm.elements.court
  const topic = agentDevelopmentForm.elements.topic

  function filterTopics() {
    for (const option of topic.options) {
      const unavailable = Boolean(
        court.value && option.value && option.dataset.court !== court.value
      )
      option.hidden = unavailable
      option.disabled = unavailable
    }
    if (topic.selectedOptions[0]?.disabled) topic.value = ''
  }

  court.addEventListener('change', filterTopics)
  filterTopics()
}
