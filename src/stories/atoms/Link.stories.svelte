<script module>
	import { defineMeta } from '@storybook/addon-svelte-csf';
	import Link from './Link.svelte';

	const { Story } = defineMeta({
		title: 'Atoms/Link',
		component: Link,
		tags: ['autodocs'],
		argTypes: {
			href: {
				control: 'text',
				description: 'Link URL'
			},
			target: {
				control: { type: 'select' },
				options: ['_self', '_blank', '_parent', '_top'],
				description: 'Link target'
			},
			variant: {
				control: { type: 'select' },
				options: ['default', 'primary', 'secondary', 'unstyled'],
				description: 'Link style variant'
			},
			showExternalIcon: {
				control: 'boolean',
				description: 'Show external link icon'
			}
		},
		parameters: {
			docs: {
				description: {
					component:
						'Accessible link component with multiple variants. Automatically handles external links with proper rel attributes. Meets WCAG 2.1 AA standards with proper focus indicators and touch targets.'
				}
			}
		}
	});
</script>

<Story name="Default" args={{ href: '#', children: 'Default Link' }}>
	<Link href="#">Default Link</Link>
</Story>

<Story name="Primary Variant">
	<Link href="#" variant="primary">Primary Link</Link>
</Story>

<Story name="Secondary Variant">
	<Link href="#" variant="secondary">Secondary Link</Link>
</Story>

<Story name="Unstyled Variant">
	<Link href="#" variant="unstyled">Unstyled Link</Link>
</Story>

<Story name="External Link">
	<Link href="https://lucide.dev" target="_blank" showExternalIcon={true}>Visit Lucide Icons</Link>
</Story>

<Story name="Internal Link">
	<Link href="/about">About Page</Link>
</Story>

<Story name="All Variants">
	<div style="display: flex; flex-direction: column; gap: var(--cr-space-md); max-width: 400px;">
		<div>
			<div class="cr-body-sm" style="margin-bottom: var(--cr-space-2); color: var(--cr-muted);">
				Default
			</div>
			<Link href="#">Regular link to internal page</Link>
		</div>

		<div>
			<div class="cr-body-sm" style="margin-bottom: var(--cr-space-2); color: var(--cr-muted);">
				Primary
			</div>
			<Link href="#" variant="primary">Important call-to-action link</Link>
		</div>

		<div>
			<div class="cr-body-sm" style="margin-bottom: var(--cr-space-2); color: var(--cr-muted);">
				Secondary
			</div>
			<Link href="#" variant="secondary">Subtle secondary link</Link>
		</div>

		<div>
			<div class="cr-body-sm" style="margin-bottom: var(--cr-space-2); color: var(--cr-muted);">
				Unstyled
			</div>
			<Link href="#" variant="unstyled">Minimal styling link</Link>
		</div>

		<div>
			<div class="cr-body-sm" style="margin-bottom: var(--cr-space-2); color: var(--cr-muted);">
				External with Icon
			</div>
			<Link href="https://example.com" target="_blank" showExternalIcon={true}>
				External resource
			</Link>
		</div>
	</div>
</Story>

<Story name="In Context">
	<div style="max-width: 600px;">
		<p class="cr-body-reg">
			This is a paragraph with a <Link href="#">regular link</Link> and an
			<Link href="https://example.com" target="_blank" showExternalIcon={true}>external link</Link>
			embedded in the text. You can also have a
			<Link href="#" variant="primary">primary link</Link>
			for emphasis.
		</p>
	</div>
</Story>

<Story name="List of Links">
	<div style="max-width: 400px;">
		<div class="cr-title-sm" style="margin-bottom: var(--cr-space-md);">Helpful Resources</div>
		<ul
			style="list-style: none; padding: 0; display: flex; flex-direction: column; gap: var(--cr-space-3);"
		>
			<li>
				<Link href="#">Legal aid referral link</Link>
			</li>
			<li>
				<Link href="#">Probono/Bar Association referral link</Link>
			</li>
			<li>
				<Link href="#">Link to Civil/Appeals division</Link>
			</li>
			<li>
				<Link href="https://courts.gov" target="_blank" showExternalIcon={true}>Court website</Link>
			</li>
		</ul>
	</div>
</Story>

<Story name="Accessibility Example">
	<div style="max-width: 500px; display: flex; flex-direction: column; gap: var(--cr-space-md);">
		<div class="cr-body-reg">
			<strong>Accessible Link Practices:</strong>
		</div>

		<div>
			<div class="cr-body-sm" style="margin-bottom: var(--cr-space-2);">
				✅ Good: Descriptive link text
			</div>
			<Link href="#">Download the court forms (PDF, 2MB)</Link>
		</div>

		<div>
			<div class="cr-body-sm" style="margin-bottom: var(--cr-space-2);">
				✅ Good: Clear external link indication
			</div>
			<Link href="https://example.com" target="_blank" showExternalIcon={true}>
				View on external site
			</Link>
		</div>

		<div>
			<div
				class="cr-body-sm"
				style="margin-bottom: var(--cr-space-2); color: var(--cr-support-error-fg);"
			>
				❌ Avoid: Generic "click here"
			</div>
			<span class="cr-body-reg">
				For more information,
				<Link href="#" variant="secondary">click here</Link>
			</span>
		</div>
	</div>
</Story>
