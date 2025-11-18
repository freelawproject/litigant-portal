<script module>
	import { defineMeta } from '@storybook/addon-svelte-csf';

	const { Story } = defineMeta({
		title: 'Style Guide/Spacing',
		parameters: {
			layout: 'fullscreen',
			docs: {
				description: {
					component:
						'Spacing system with 4px base unit, numeric scale, semantic scale, and usage guidelines'
				}
			}
		},
		tags: ['autodocs']
	});
</script>

<Story name="Documentation">
	<div class="sg-section">
		<h2>Spacing System</h2>

		<!-- Spacing Introduction -->
		<div class="sg-card sg-margin-bottom-lg">
			<h3>Spacing System Overview</h3>
			<div class="sg-card-content">
				<p class="cr-body-reg sg-margin-bottom">
					Litigant Portal uses a consistent 4px base spacing unit to create harmonious layouts. All
					spacing values are multiples of this base unit, ensuring visual rhythm and consistency
					across the interface.
				</p>
				<p class="cr-body-reg">
					<strong>Base Unit:</strong> 4px • <strong>Scale:</strong> Exponential progression for optimal
					visual hierarchy
				</p>
			</div>
		</div>

		<!-- Spacing Scale -->
		<div class="sg-spacing-section">
			<h2>Spacing Scale</h2>

			<div class="sg-component-grid">
				<!-- Numeric Scale -->
				<div class="sg-example-card">
					<h3>Numeric Scale</h3>
					<div class="sg-spacing-grid">
						<div class="sg-spacing-row">
							<span class="sg-spacing-label">cr-space-1</span>
							<div class="sg-spacing-bar sg-spacing-bar-xs"></div>
							<span class="sg-spacing-value">4px</span>
						</div>
						<div class="sg-spacing-row">
							<span class="sg-spacing-label">cr-space-2</span>
							<div class="sg-spacing-bar sg-spacing-bar-sm"></div>
							<span class="sg-spacing-value">8px</span>
						</div>
						<div class="sg-spacing-row">
							<span class="sg-spacing-label">cr-space-3</span>
							<div class="sg-spacing-bar sg-spacing-bar-3"></div>
							<span class="sg-spacing-value">12px</span>
						</div>
						<div class="sg-spacing-row">
							<span class="sg-spacing-label">cr-space-4</span>
							<div class="sg-spacing-bar sg-spacing-bar-md"></div>
							<span class="sg-spacing-value">16px</span>
						</div>
						<div class="sg-spacing-row">
							<span class="sg-spacing-label">cr-space-6</span>
							<div class="sg-spacing-bar sg-spacing-bar-lg"></div>
							<span class="sg-spacing-value">24px</span>
						</div>
						<div class="sg-spacing-row">
							<span class="sg-spacing-label">cr-space-8</span>
							<div class="sg-spacing-bar sg-spacing-bar-xl"></div>
							<span class="sg-spacing-value">32px</span>
						</div>
						<div class="sg-spacing-row">
							<span class="sg-spacing-label">cr-space-12</span>
							<div class="sg-spacing-bar sg-spacing-bar-2xl"></div>
							<span class="sg-spacing-value">48px</span>
						</div>
						<div class="sg-spacing-row">
							<span class="sg-spacing-label">cr-space-16</span>
							<div class="sg-spacing-bar sg-spacing-bar-3xl"></div>
							<span class="sg-spacing-value">64px</span>
						</div>
					</div>
				</div>

				<!-- Semantic Scale -->
				<div class="sg-example-card">
					<h3>Semantic Scale</h3>
					<div class="sg-spacing-grid">
						<div class="sg-spacing-row">
							<span class="sg-spacing-label-wide">cr-space-xs</span>
							<div class="sg-spacing-bar-secondary sg-spacing-bar-xs"></div>
							<span class="sg-spacing-value">4px - Tight spacing</span>
						</div>
						<div class="sg-spacing-row">
							<span class="sg-spacing-label-wide">cr-space-sm</span>
							<div class="sg-spacing-bar-secondary sg-spacing-bar-sm"></div>
							<span class="sg-spacing-value">8px - Small spacing</span>
						</div>
						<div class="sg-spacing-row">
							<span class="sg-spacing-label-wide">cr-space-md</span>
							<div class="sg-spacing-bar-secondary sg-spacing-bar-md"></div>
							<span class="sg-spacing-value">16px - Medium spacing</span>
						</div>
						<div class="sg-spacing-row">
							<span class="sg-spacing-label-wide">cr-space-lg</span>
							<div class="sg-spacing-bar-secondary sg-spacing-bar-lg"></div>
							<span class="sg-spacing-value">24px - Large spacing</span>
						</div>
						<div class="sg-spacing-row">
							<span class="sg-spacing-label-wide">cr-space-xl</span>
							<div class="sg-spacing-bar-secondary sg-spacing-bar-xl"></div>
							<span class="sg-spacing-value">32px - Extra large</span>
						</div>
						<div class="sg-spacing-row">
							<span class="sg-spacing-label-wide">cr-space-2xl</span>
							<div class="sg-spacing-bar-secondary sg-spacing-bar-2xl"></div>
							<span class="sg-spacing-value">48px - 2X large</span>
						</div>
						<div class="sg-spacing-row">
							<span class="sg-spacing-label-wide">cr-space-3xl</span>
							<div class="sg-spacing-bar-secondary sg-spacing-bar-3xl"></div>
							<span class="sg-spacing-value">64px - 3X large</span>
						</div>
					</div>
				</div>
			</div>
		</div>

		<!-- Spacing Applications -->
		<div class="sg-spacing-section">
			<h2>Spacing Applications</h2>

			<div class="sg-component-grid">
				<!-- Padding Examples -->
				<div class="sg-example-card">
					<h3>Padding Examples</h3>
					<div class="sg-spacing-examples">
						<div class="sg-spacing-example">
							<div class="sg-eyebrow">Small Gap (8px)</div>
							<div class="sg-flex-row sg-gap-sm sg-padding-sm sg-bg-secondary-light">
								<div class="sg-spacing-demo-box sg-flex-item">Item 1</div>
								<div class="sg-spacing-demo-box sg-flex-item">Item 2</div>
								<div class="sg-spacing-demo-box sg-flex-item">Item 3</div>
							</div>
						</div>

						<div class="sg-spacing-example">
							<div class="sg-eyebrow">Medium Gap (16px)</div>
							<div class="sg-flex-row sg-gap-md sg-padding-sm sg-bg-secondary-light">
								<div class="sg-spacing-demo-box sg-flex-item">Item 1</div>
								<div class="sg-spacing-demo-box sg-flex-item">Item 2</div>
								<div class="sg-spacing-demo-box sg-flex-item">Item 3</div>
							</div>
						</div>

						<div class="sg-spacing-example">
							<div class="sg-eyebrow">Large Gap (24px)</div>
							<div class="sg-flex-row sg-gap-lg sg-padding-sm sg-bg-secondary-light">
								<div class="sg-spacing-demo-box sg-flex-item">Item 1</div>
								<div class="sg-spacing-demo-box sg-flex-item">Item 2</div>
								<div class="sg-spacing-demo-box sg-flex-item">Item 3</div>
							</div>
						</div>
					</div>
				</div>
			</div>
		</div>

		<!-- Usage Guidelines -->
		<div class="sg-card sg-margin-top-lg">
			<h2>Spacing Usage Guidelines</h2>
			<div class="sg-card-content">
				<div class="sg-component-grid">
					<div>
						<div class="cr-body-reg sg-margin-bottom">
							<strong>Component Padding:</strong> Use --cr-space-md (16px) for standard component internal
							spacing
						</div>

						<div class="cr-body-reg sg-margin-bottom">
							<strong>Element Margins:</strong> Use --cr-space-lg (24px) for spacing between related
							components
						</div>

						<div class="cr-body-reg">
							<strong>Section Gaps:</strong> Use --cr-space-2xl (48px) for major section divisions
						</div>
					</div>

					<div>
						<div class="cr-body-reg sg-margin-bottom">
							<strong>Button Groups:</strong> Use --cr-space-3 (12px) gap between related buttons
						</div>

						<div class="cr-body-reg sg-margin-bottom">
							<strong>Form Fields:</strong> Use --cr-space-4 (16px) margin between form elements
						</div>

						<div class="cr-body-reg">
							<strong>Text Spacing:</strong> Use --cr-space-2 to --cr-space-4 for text element margins
						</div>
					</div>
				</div>

				<div class="sg-tip-box sg-margin-top-lg">
					<div class="cr-body-sm sg-tip-text">
						<strong>Pro Tip:</strong> Always use spacing variables instead of hardcoded pixel values.
						This ensures consistency and makes it easy to adjust spacing globally across the design system.
					</div>
				</div>
			</div>
		</div>
	</div>
</Story>

<style>
	/* Import the chirp-radio style guide CSS classes */
	/* These styles are defined in the main project's CSS */
</style>
