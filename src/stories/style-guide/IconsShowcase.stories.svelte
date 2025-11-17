<script module>
	import { defineMeta } from '@storybook/addon-svelte-csf';

	const { Story } = defineMeta({
		title: 'Style Guide/Icons',
		parameters: {
			layout: 'fullscreen',
			docs: {
				description: {
					component:
						'Icon system documentation - placeholder for icon library integration (Phosphor, Font Awesome, or similar)'
				}
			}
		},
		tags: ['autodocs']
	});

	const codeExample =
		"<!-- Svelte with Lucide -->\n<script>\n  import { ArrowRight, Heart, Music } from 'lucide-svelte';\n<" +
		'/script>\n\n<button>\n  Continue\n  <ArrowRight size={20} />\n</button>\n\n<!-- With ARIA label -->\n<button aria-label="Add to favorites">\n  <Heart size={24} />\n</button>';
</script>

<Story name="Documentation">
	<div class="sg-section">
		<div class="sg-header" style="text-align: center; margin-bottom: var(--cr-space-8);">
			<h1 style="font: var(--cr-title-xl); color: var(--cr-ink); margin: 0 0 var(--cr-space-4) 0;">
				Icons Documentation
			</h1>
			<p
				style="font: var(--cr-body-reg); color: var(--cr-default-700); max-width: 600px; margin: 0 auto;"
			>
				Complete icon library for navigation, actions, content, and UI elements. This is a
				placeholder - integrate your preferred icon library (Phosphor Icons, Font Awesome, Lucide,
				etc.)
			</p>
		</div>

		<!-- Icon Categories Overview -->
		<div class="sg-component-grid">
			<div class="sg-example-card">
				<h2 class="sg-card-title">Icon Categories</h2>
				<div style="display: flex; flex-direction: column; gap: var(--cr-space-3);">
					<div class="cr-body-reg">
						<strong>Navigation & Actions:</strong> Arrows, carets, close, search, menu, plus/minus
					</div>
					<div class="cr-body-reg">
						<strong>Calendar & Events:</strong> Calendar variants, ticket, scheduling
					</div>
					<div class="cr-body-reg">
						<strong>Music & Media:</strong> Vinyl, notes, playlist, play/pause, headphones, microphone
					</div>
					<div class="cr-body-reg">
						<strong>User & Social:</strong> Heart, user, chat, sign-in, share
					</div>
					<div class="cr-body-reg">
						<strong>Content & Documents:</strong> Notepad, paperclip, newspaper, map
					</div>
					<div class="cr-body-reg">
						<strong>Communication:</strong> Paper plane, messaging icons
					</div>
					<div class="cr-body-reg">
						<strong>Settings & Tools:</strong> Gear, save, pencil, upload
					</div>
					<div class="cr-body-reg">
						<strong>Shopping:</strong> Shopping bag, storefront
					</div>
					<div class="cr-body-reg">
						<strong>Visibility:</strong> Eye, download, export
					</div>
					<div class="cr-body-reg">
						<strong>Collection:</strong> Plus/check circles and squares
					</div>
					<div class="cr-body-reg">
						<strong>Alerts & Status:</strong> Info, warning circle
					</div>
				</div>
			</div>

			<div class="sg-example-card">
				<h2 class="sg-card-title">Usage Guidelines</h2>
				<div style="display: flex; flex-direction: column; gap: var(--cr-space-3);">
					<div class="cr-body-reg">
						<strong>Sizing:</strong> Use consistent sizes - 16px (small), 24px (medium), 32px (large),
						48px+ (hero)
					</div>
					<div class="cr-body-reg">
						<strong>Color:</strong> Match text color or use brand colors for emphasis. Icons should inherit
						currentColor by default
					</div>
					<div class="cr-body-reg">
						<strong>Spacing:</strong> Maintain 8-12px spacing between icons and adjacent text
					</div>
					<div class="cr-body-reg">
						<strong>Accessibility:</strong> Always provide aria-labels or sr-only text for icon-only
						buttons
					</div>
					<div class="cr-body-reg">
						<strong>Social Icons:</strong> Facebook, Instagram, Twitter, LinkedIn, Bluesky
					</div>
				</div>
			</div>
		</div>

		<!-- Icon Library Integration Note -->
		<div class="sg-card sg-margin-top-lg">
			<h2>Icon Library Integration</h2>
			<div class="sg-card-content">
				<div class="cr-body-reg sg-margin-bottom">
					<strong>Recommended Libraries:</strong>
				</div>
				<div style="display: flex; flex-direction: column; gap: var(--cr-space-2);">
					<div class="cr-body-sm">
						• <strong>Phosphor Icons</strong> (react-icons/pi) - Used in CHIRP Radio, comprehensive set
					</div>
					<div class="cr-body-sm">
						• <strong>Lucide</strong> (lucide-svelte) - Clean, consistent, Svelte-native
					</div>
					<div class="cr-body-sm">
						• <strong>Heroicons</strong> - Tailwind's icon set, good for UI
					</div>
					<div class="cr-body-sm">
						• <strong>Font Awesome</strong> - Extensive library with social icons
					</div>
				</div>

				<div class="sg-tip-box sg-margin-top-lg">
					<div class="cr-body-sm sg-tip-text">
						<strong>Pro Tip:</strong> Choose one primary icon library and stick with it for consistency.
						Add Font Awesome only if needed for specific social media icons not available in your primary
						library.
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
