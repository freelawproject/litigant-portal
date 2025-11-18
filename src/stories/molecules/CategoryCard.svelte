<script lang="ts">
	import './categoryCard.css';

	interface Props {
		/** Primary label (e.g., "Unlawful Detainer") */
		label: string;
		/** Secondary label/subtitle (e.g., "Eviction") */
		subtitle: string;
		/** Whether the card is selected */
		selected?: boolean;
		/** Whether the card is disabled */
		disabled?: boolean;
		/** Click event handler */
		onclick?: (event: MouseEvent & { currentTarget: HTMLButtonElement }) => void;
		/** Additional CSS classes */
		class?: string;
	}

	let {
		label,
		subtitle,
		selected = false,
		disabled = false,
		onclick,
		class: className = '',
		...props
	}: Props = $props();

	let classList = $derived(
		[
			'category-card',
			selected && 'category-card--selected',
			disabled && 'category-card--disabled',
			className
		]
			.filter(Boolean)
			.join(' ')
	);
</script>

<button
	type="button"
	class={classList}
	{disabled}
	{onclick}
	aria-pressed={selected ? 'true' : 'false'}
	{...props}
>
	<div class="category-card__label">{label}</div>
	<div class="category-card__subtitle">{subtitle}</div>
</button>
