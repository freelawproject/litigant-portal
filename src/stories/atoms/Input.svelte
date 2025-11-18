<script lang="ts">
	import './input.css';

	interface Props {
		/** Input type */
		type?: 'text' | 'email' | 'tel' | 'url' | 'password' | 'search';
		/** Input value */
		value?: string;
		/** Placeholder text */
		placeholder?: string;
		/** Input name attribute */
		name?: string;
		/** Input ID for label association */
		id?: string;
		/** Whether the input is disabled */
		disabled?: boolean;
		/** Whether the input is readonly */
		readonly?: boolean;
		/** Whether the input is required */
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
		/** Input event handler */
		oninput?: (event: Event & { currentTarget: HTMLInputElement }) => void;
		/** Change event handler */
		onchange?: (event: Event & { currentTarget: HTMLInputElement }) => void;
		/** Focus event handler */
		onfocus?: (event: FocusEvent & { currentTarget: HTMLInputElement }) => void;
		/** Blur event handler */
		onblur?: (event: FocusEvent & { currentTarget: HTMLInputElement }) => void;
	}

	let {
		type = 'text',
		value = $bindable(''),
		placeholder,
		name,
		id,
		disabled = false,
		readonly = false,
		required = false,
		error = false,
		success = false,
		ariaLabel,
		ariaDescribedby,
		class: className = '',
		oninput,
		onchange,
		onfocus,
		onblur,
		...props
	}: Props = $props();

	let classList = $derived(
		[
			'input',
			error && 'input--error',
			success && 'input--success',
			disabled && 'input--disabled',
			readonly && 'input--readonly',
			className
		]
			.filter(Boolean)
			.join(' ')
	);
</script>

<input
	{type}
	bind:value
	{placeholder}
	{name}
	{id}
	{disabled}
	{readonly}
	{required}
	class={classList}
	aria-label={ariaLabel}
	aria-describedby={ariaDescribedby}
	aria-invalid={error ? 'true' : undefined}
	{oninput}
	{onchange}
	{onfocus}
	{onblur}
	{...props}
/>
