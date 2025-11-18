<script lang="ts">
	import './button.css';
	import type { Snippet } from 'svelte';

	interface Props {
		/** Button variant */
		variant?: 'primary' | 'secondary' | 'tertiary' | 'ghost';
		/** Button type */
		type?: 'button' | 'submit' | 'reset';
		/** Whether the button is disabled */
		disabled?: boolean;
		/** Whether the button takes full width */
		fullWidth?: boolean;
		/** Button ID for label association */
		id?: string;
		/** Accessible label (if children not sufficient) */
		ariaLabel?: string;
		/** Additional CSS classes */
		class?: string;
		/** Click event handler */
		onclick?: (event: MouseEvent & { currentTarget: HTMLButtonElement }) => void;
		/** Focus event handler */
		onfocus?: (event: FocusEvent & { currentTarget: HTMLButtonElement }) => void;
		/** Blur event handler */
		onblur?: (event: FocusEvent & { currentTarget: HTMLButtonElement }) => void;
		/** Button content */
		children?: Snippet;
	}

	let {
		variant = 'primary',
		type = 'button',
		disabled = false,
		fullWidth = false,
		id,
		ariaLabel,
		class: className = '',
		onclick,
		onfocus,
		onblur,
		children,
		...props
	}: Props = $props();

	let classList = $derived(
		['button', `button--${variant}`, fullWidth && 'button--full-width', className]
			.filter(Boolean)
			.join(' ')
	);
</script>

<button
	{type}
	{id}
	{disabled}
	class={classList}
	aria-label={ariaLabel}
	{onclick}
	{onfocus}
	{onblur}
	{...props}
>
	{#if children}
		{@render children()}
	{/if}
</button>
