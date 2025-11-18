<script module>
	import { defineMeta } from '@storybook/addon-svelte-csf';

	const { Story } = defineMeta({
		title: 'Style Guide/Icons',
		parameters: {
			layout: 'fullscreen',
			docs: {
				description: {
					component:
						'Icon system using Lucide - a beautiful, consistent icon library for Svelte applications.'
				}
			}
		},
		tags: ['autodocs']
	});
</script>

<script>
	const codeExample =
		`<` +
		`script>
  import { Search, ChevronDown, Mail } from '@lucide/svelte';
<` +
		`/script>

<!-- Basic usage -->
<Search size={24} />

<!-- With custom color -->
<ChevronDown size={32} color="var(--cr-primary-500)" />

<!-- In a button -->
<button>
  Send Message
  <Mail size={20} />
</button>`;

	const commonIcons = [
		{ name: 'Search', description: 'Search functionality' },
		{ name: 'Scale', description: 'Legal/justice symbol' },
		{ name: 'ChevronDown', description: 'Dropdown indicators' },
		{ name: 'Smartphone', description: 'Mobile device' },
		{ name: 'Mail', description: 'Email/messaging' },
		{ name: 'User', description: 'User profile' },
		{ name: 'FileText', description: 'Documents' },
		{ name: 'AlertCircle', description: 'Warnings/alerts' },
		{ name: 'CheckCircle', description: 'Success states' },
		{ name: 'Info', description: 'Information' },
		{ name: 'Home', description: 'Home/navigation' }
	];
</script>

<Story name="Documentation">
	<div class="sg-section">
		<div class="sg-header" style="text-align: center; margin-bottom: var(--cr-space-8);">
			<h1 style="font: var(--cr-title-xl); color: var(--cr-ink); margin: 0 0 var(--cr-space-4) 0;">
				Icons
			</h1>
			<p
				style="font: var(--cr-body-reg); color: var(--cr-default-700); max-width: 600px; margin: 0 auto;"
			>
				Using Lucide icons - a beautiful, consistent icon library with over 1,400 icons. Import
				directly from <code>@lucide/svelte</code> and use as components.
			</p>
		</div>

		<!-- Common Icons Preview -->
		<div class="sg-card sg-margin-bottom-lg">
			<h2>Common Icons Used</h2>
			<div
				style="display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: var(--cr-space-lg); padding: var(--cr-space-lg);"
			>
				{#each commonIcons as icon (icon.name)}
					<div style="text-align: center; padding: var(--cr-space-3);">
						<code
							class="cr-body-sm"
							style="display: block; font-weight: 600; margin-bottom: var(--cr-space-1);"
						>
							{icon.name}
						</code>
						<div class="cr-body-xs" style="color: var(--cr-default-600);">{icon.description}</div>
					</div>
				{/each}
			</div>
		</div>

		<!-- Usage Guidelines -->
		<div class="sg-component-grid">
			<div class="sg-example-card">
				<h2 class="sg-card-title">Usage Guidelines</h2>
				<div style="display: flex; flex-direction: column; gap: var(--cr-space-3);">
					<div class="cr-body-reg">
						<strong>Sizing:</strong> Standard sizes are 16px (xs), 20px (sm), 24px (md), 32px (lg), 48px
						(xl)
					</div>
					<div class="cr-body-reg">
						<strong>Color:</strong> Icons inherit currentColor by default. Use design tokens for brand
						colors
					</div>
					<div class="cr-body-reg">
						<strong>Stroke Width:</strong> Default is 2, can be adjusted (1-3) for visual weight
					</div>
					<div class="cr-body-reg">
						<strong>Accessibility:</strong> Icons in buttons should have aria-labels or visible text
					</div>
				</div>
			</div>

			<div class="sg-example-card">
				<h2 class="sg-card-title">Resources</h2>
				<div style="display: flex; flex-direction: column; gap: var(--cr-space-3);">
					<div class="cr-body-reg">
						<strong>Browse all icons:</strong>
						<br />
						<a
							href="https://lucide.dev/icons"
							target="_blank"
							rel="noopener noreferrer"
							style="color: var(--cr-primary-500);"
						>
							lucide.dev/icons
						</a>
					</div>
					<div class="cr-body-reg">
						<strong>Documentation:</strong>
						<br />
						<a
							href="https://lucide.dev/guide/packages/lucide-svelte"
							target="_blank"
							rel="noopener noreferrer"
							style="color: var(--cr-primary-500);"
						>
							Lucide Svelte Guide
						</a>
					</div>
					<div class="cr-body-reg">
						<strong>Package:</strong>
						<br />
						<code>@lucide/svelte</code>
					</div>
				</div>
			</div>
		</div>

		<!-- Example Icon Usage -->
		<div class="sg-card sg-margin-top-lg">
			<h2>Code Example</h2>
			<div class="sg-code-box">
				<pre style="margin: 0; color: var(--cr-paper); line-height: 1.6;">{codeExample}</pre>
			</div>
		</div>
	</div>
</Story>

<style>
	/* Styles are imported from design-tokens.css and style-guide.css */
</style>
