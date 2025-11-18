<script lang="ts">
	import './link.css';
	import type { Snippet } from 'svelte';

	interface Props {
		/** Link href */
		href: string;
		/** Link target (_blank for external links) */
		target?: '_blank' | '_self' | '_parent' | '_top';
		/** Rel attribute (automatically set to 'noopener noreferrer' for external links) */
		rel?: string;
		/** Link variant style */
		variant?: 'default' | 'primary' | 'secondary' | 'unstyled';
		/** Whether to show external link icon */
		showExternalIcon?: boolean;
		/** Additional CSS classes */
		class?: string;
		/** Click event handler */
		onclick?: (event: MouseEvent & { currentTarget: HTMLAnchorElement }) => void;
		/** Link content */
		children?: Snippet;
	}

	let {
		href,
		target,
		rel,
		variant = 'default',
		showExternalIcon = false,
		class: className = '',
		onclick,
		children,
		...props
	}: Props = $props();

	// Auto-detect external links and set appropriate rel
	const isExternal = $derived(
		target === '_blank' || href.startsWith('http://') || href.startsWith('https://')
	);

	const relValue = $derived(rel || (isExternal ? 'noopener noreferrer' : undefined));

	const classList = $derived(['link', `link--${variant}`, className].filter(Boolean).join(' '));
</script>

<!-- eslint-disable-next-line svelte/no-navigation-without-resolve -->
<a {href} {target} rel={relValue} class={classList} {onclick} {...props}>
	{#if children}
		{@render children()}
	{/if}
	{#if showExternalIcon && isExternal}
		<svg
			xmlns="http://www.w3.org/2000/svg"
			width="14"
			height="14"
			viewBox="0 0 24 24"
			fill="none"
			stroke="currentColor"
			stroke-width="2"
			stroke-linecap="round"
			stroke-linejoin="round"
			class="link-external-icon"
			aria-hidden="true"
		>
			<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>
			<polyline points="15 3 21 3 21 9"></polyline>
			<line x1="10" y1="14" x2="21" y2="3"></line>
		</svg>
	{/if}
</a>
