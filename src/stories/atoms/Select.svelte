<script lang="ts">
	import './select.css';
	import { ChevronDown } from '@lucide/svelte';
	import type { Snippet } from 'svelte';

	interface Props {
		/** Select value */
		value?: string;
		/** Select name attribute */
		name?: string;
		/** Select ID for label association */
		id?: string;
		/** Whether the select is disabled */
		disabled?: boolean;
		/** Whether the select is required */
		required?: boolean;
		/** Error state */
		error?: boolean;
		/** Success state */
		success?: boolean;
		/** Accessible label (required for accessibility) */
		ariaLabel?: string;
		/** Described by (for error messages) */
		ariaDescribedby?: string;
		/** Additional CSS classes */
		class?: string;
		/** Change event handler */
		onchange?: (event: Event & { currentTarget: HTMLSelectElement }) => void;
		/** Focus event handler */
		onfocus?: (event: FocusEvent & { currentTarget: HTMLSelectElement }) => void;
		/** Blur event handler */
		onblur?: (event: FocusEvent & { currentTarget: HTMLSelectElement }) => void;
		/** Option elements */
		children?: Snippet;
	}

	let {
		value = $bindable(''),
		name,
		id,
		disabled = false,
		required = false,
		error = false,
		success = false,
		ariaLabel,
		ariaDescribedby,
		class: className = '',
		onchange,
		onfocus,
		onblur,
		children,
		...props
	}: Props = $props();

	let classList = $derived(
		[
			'select-wrapper',
			error && 'select-wrapper--error',
			success && 'select-wrapper--success',
			disabled && 'select-wrapper--disabled',
			className
		]
			.filter(Boolean)
			.join(' ')
	);
</script>

<div class={classList}>
	<select
		bind:value
		{name}
		{id}
		{disabled}
		{required}
		class="select"
		aria-label={ariaLabel}
		aria-describedby={ariaDescribedby}
		aria-invalid={error ? 'true' : undefined}
		{onchange}
		{onfocus}
		{onblur}
		{...props}
	>
		{#if children}
			{@render children()}
		{/if}
	</select>
	<ChevronDown size={20} class="select-icon" />
</div>
