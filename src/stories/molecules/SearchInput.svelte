<script lang="ts">
	import './searchInput.css';
	import { Search } from '@lucide/svelte';

	interface Props {
		/** Search input value */
		value?: string;
		/** Placeholder text */
		placeholder?: string;
		/** Whether the input is disabled */
		disabled?: boolean;
		/** Whether the input is required */
		required?: boolean;
		/** Input ID for label association */
		id?: string;
		/** Accessible label (required for accessibility) */
		ariaLabel: string;
		/** Additional CSS classes */
		class?: string;
		/** Change event handler */
		onchange?: (event: Event & { currentTarget: HTMLInputElement }) => void;
		/** Input event handler */
		oninput?: (event: Event & { currentTarget: HTMLInputElement }) => void;
		/** Focus event handler */
		onfocus?: (event: FocusEvent & { currentTarget: HTMLInputElement }) => void;
		/** Blur event handler */
		onblur?: (event: FocusEvent & { currentTarget: HTMLInputElement }) => void;
		/** Submit event handler (called when user presses Enter) */
		onsubmit?: () => void;
	}

	let {
		value = $bindable(''),
		placeholder = 'Search...',
		disabled = false,
		required = false,
		id,
		ariaLabel,
		class: className = '',
		onchange,
		oninput,
		onfocus,
		onblur,
		onsubmit,
		...props
	}: Props = $props();

	let classList = $derived(['search-input', className].filter(Boolean).join(' '));

	function handleKeydown(event: KeyboardEvent) {
		if (event.key === 'Enter' && onsubmit) {
			event.preventDefault();
			onsubmit();
		}
	}
</script>

<div class={classList}>
	<Search size={20} class="search-input__icon" />
	<input
		bind:value
		type="search"
		{id}
		{placeholder}
		{disabled}
		{required}
		class="search-input__field"
		aria-label={ariaLabel}
		{onchange}
		{oninput}
		{onfocus}
		{onblur}
		onkeydown={handleKeydown}
		{...props}
	/>
</div>
