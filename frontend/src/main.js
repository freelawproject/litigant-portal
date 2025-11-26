// Import styles first
import './styles/main.css';

// Import Alpine
import Alpine from 'alpinejs';

// Import Alpine stores
import { themeStore } from './scripts/stores/theme';

// Import Alpine components
// import { searchInput } from './scripts/components/searchInput';

// Register stores
Alpine.store('theme', themeStore);

// Register components
// Alpine.data('searchInput', searchInput);

// Initialize Alpine
window.Alpine = Alpine;
Alpine.start();

// Initialize theme on load
document.addEventListener('DOMContentLoaded', () => {
  Alpine.store('theme').init();
});
