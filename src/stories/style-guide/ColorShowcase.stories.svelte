<script module>
	import { defineMeta } from '@storybook/addon-svelte-csf';

	const { Story } = defineMeta({
		title: 'Style Guide/Colors',
		parameters: {
			layout: 'fullscreen',
			docs: {
				description: {
					component: 'Complete color palette documentation with semantic color groups'
				}
			}
		},
		tags: ['autodocs']
	});
</script>

<Story name="Documentation">
	<div class="sg-section">
		<div class="sg-header">
			<h1>Colors</h1>
			<p class="sg-description">
				Complete color palette with semantic groupings. Each color includes a visual preview, name,
				and CSS variable reference.
			</p>
		</div>

		<!-- Primary Colors -->
		<section class="sg-color-group">
			<h2>Primary Colors</h2>
			<div class="sg-color-swatches">
				<div class="sg-color-swatch">
					<div class="sg-color-rectangle" style="background-color: var(--cr-primary-900);"></div>
					<div class="sg-color-info">
						<div class="sg-color-name">Primary 900</div>
						<div class="sg-color-value">--cr-primary-900</div>
					</div>
				</div>
				<div class="sg-color-swatch">
					<div class="sg-color-rectangle" style="background-color: var(--cr-primary-700);"></div>
					<div class="sg-color-info">
						<div class="sg-color-name">Primary 700</div>
						<div class="sg-color-value">--cr-primary-700</div>
					</div>
				</div>
				<div class="sg-color-swatch">
					<div class="sg-color-rectangle" style="background-color: var(--cr-primary-500);"></div>
					<div class="sg-color-info">
						<div class="sg-color-name">Primary 500</div>
						<div class="sg-color-value">--cr-primary-500</div>
					</div>
				</div>
				<div class="sg-color-swatch">
					<div class="sg-color-rectangle" style="background-color: var(--cr-primary-300);"></div>
					<div class="sg-color-info">
						<div class="sg-color-name">Primary 300</div>
						<div class="sg-color-value">--cr-primary-300</div>
					</div>
				</div>
				<div class="sg-color-swatch">
					<div
						class="sg-color-rectangle sg-border-light"
						style="background-color: var(--cr-primary-100);"
					></div>
					<div class="sg-color-info">
						<div class="sg-color-name">Primary 100</div>
						<div class="sg-color-value">--cr-primary-100</div>
					</div>
				</div>
			</div>
		</section>

		<!-- Secondary Colors -->
		<section class="sg-color-group">
			<h2>Secondary Colors</h2>
			<div class="sg-color-swatches">
				<div class="sg-color-swatch">
					<div class="sg-color-rectangle" style="background-color: var(--cr-secondary-900);"></div>
					<div class="sg-color-info">
						<div class="sg-color-name">Secondary 900</div>
						<div class="sg-color-value">--cr-secondary-900</div>
					</div>
				</div>
				<div class="sg-color-swatch">
					<div class="sg-color-rectangle" style="background-color: var(--cr-secondary-700);"></div>
					<div class="sg-color-info">
						<div class="sg-color-name">Secondary 700</div>
						<div class="sg-color-value">--cr-secondary-700</div>
					</div>
				</div>
				<div class="sg-color-swatch">
					<div class="sg-color-rectangle" style="background-color: var(--cr-secondary-500);"></div>
					<div class="sg-color-info">
						<div class="sg-color-name">Secondary 500</div>
						<div class="sg-color-value">--cr-secondary-500</div>
					</div>
				</div>
				<div class="sg-color-swatch">
					<div class="sg-color-rectangle" style="background-color: var(--cr-secondary-300);"></div>
					<div class="sg-color-info">
						<div class="sg-color-name">Secondary 300</div>
						<div class="sg-color-value">--cr-secondary-300</div>
					</div>
				</div>
				<div class="sg-color-swatch">
					<div
						class="sg-color-rectangle sg-border-light"
						style="background-color: var(--cr-secondary-100);"
					></div>
					<div class="sg-color-info">
						<div class="sg-color-name">Secondary 100</div>
						<div class="sg-color-value">--cr-secondary-100</div>
					</div>
				</div>
			</div>
		</section>

		<!-- Neutral Colors -->
		<section class="sg-color-group">
			<h2>Neutral Colors</h2>
			<div class="sg-color-swatches">
				<div class="sg-color-swatch">
					<div class="sg-color-rectangle" style="background-color: var(--cr-default-900);"></div>
					<div class="sg-color-info">
						<div class="sg-color-name">Neutral 900</div>
						<div class="sg-color-value">--cr-default-900</div>
					</div>
				</div>
				<div class="sg-color-swatch">
					<div class="sg-color-rectangle" style="background-color: var(--cr-default-700);"></div>
					<div class="sg-color-info">
						<div class="sg-color-name">Neutral 700</div>
						<div class="sg-color-value">--cr-default-700</div>
					</div>
				</div>
				<div class="sg-color-swatch">
					<div class="sg-color-rectangle" style="background-color: var(--cr-default-500);"></div>
					<div class="sg-color-info">
						<div class="sg-color-name">Neutral 500</div>
						<div class="sg-color-value">--cr-default-500</div>
					</div>
				</div>
				<div class="sg-color-swatch">
					<div class="sg-color-rectangle" style="background-color: var(--cr-default-300);"></div>
					<div class="sg-color-info">
						<div class="sg-color-name">Neutral 300</div>
						<div class="sg-color-value">--cr-default-300</div>
					</div>
				</div>
				<div class="sg-color-swatch">
					<div
						class="sg-color-rectangle sg-border-light"
						style="background-color: var(--cr-default-100);"
					></div>
					<div class="sg-color-info">
						<div class="sg-color-name">Neutral 100</div>
						<div class="sg-color-value">--cr-default-100</div>
					</div>
				</div>
			</div>
		</section>

		<!-- Surface Colors -->
		<section class="sg-color-group">
			<h2>Surface Colors</h2>
			<div class="sg-color-swatches">
				<div class="sg-color-swatch">
					<div class="sg-color-rectangle" style="background-color: var(--cr-ink);"></div>
					<div class="sg-color-info">
						<div class="sg-color-name">Ink (Dark)</div>
						<div class="sg-color-value">--cr-ink</div>
					</div>
				</div>
				<div class="sg-color-swatch">
					<div
						class="sg-color-rectangle sg-border-light"
						style="background-color: var(--cr-paper);"
					></div>
					<div class="sg-color-info">
						<div class="sg-color-name">Paper (Light)</div>
						<div class="sg-color-value">--cr-paper</div>
					</div>
				</div>
			</div>
		</section>

		<!-- Support Colors -->
		<section class="sg-color-group">
			<h2>Support Colors</h2>

			<h3 class="sg-color-subtitle">Success</h3>
			<div class="sg-color-swatches">
				<div class="sg-color-swatch">
					<div
						class="sg-color-rectangle"
						style="background-color: var(--cr-support-success-bg);"
					></div>
					<div class="sg-color-info">
						<div class="sg-color-name">Success Background</div>
						<div class="sg-color-value">--cr-support-success-bg</div>
					</div>
				</div>
				<div class="sg-color-swatch">
					<div
						class="sg-color-rectangle"
						style="background-color: var(--cr-support-success-fg);"
					></div>
					<div class="sg-color-info">
						<div class="sg-color-name">Success Foreground</div>
						<div class="sg-color-value">--cr-support-success-fg</div>
					</div>
				</div>
			</div>

			<h3 class="sg-color-subtitle">Warning</h3>
			<div class="sg-color-swatches">
				<div class="sg-color-swatch">
					<div
						class="sg-color-rectangle"
						style="background-color: var(--cr-support-warning-bg);"
					></div>
					<div class="sg-color-info">
						<div class="sg-color-name">Warning Background</div>
						<div class="sg-color-value">--cr-support-warning-bg</div>
					</div>
				</div>
				<div class="sg-color-swatch">
					<div
						class="sg-color-rectangle"
						style="background-color: var(--cr-support-warning-fg);"
					></div>
					<div class="sg-color-info">
						<div class="sg-color-name">Warning Foreground</div>
						<div class="sg-color-value">--cr-support-warning-fg</div>
					</div>
				</div>
			</div>

			<h3 class="sg-color-subtitle">Error</h3>
			<div class="sg-color-swatches">
				<div class="sg-color-swatch">
					<div
						class="sg-color-rectangle"
						style="background-color: var(--cr-support-error-bg);"
					></div>
					<div class="sg-color-info">
						<div class="sg-color-name">Error Background</div>
						<div class="sg-color-value">--cr-support-error-bg</div>
					</div>
				</div>
				<div class="sg-color-swatch">
					<div
						class="sg-color-rectangle"
						style="background-color: var(--cr-support-error-fg);"
					></div>
					<div class="sg-color-info">
						<div class="sg-color-name">Error Foreground</div>
						<div class="sg-color-value">--cr-support-error-fg</div>
					</div>
				</div>
			</div>

			<h3 class="sg-color-subtitle">Info</h3>
			<div class="sg-color-swatches">
				<div class="sg-color-swatch">
					<div
						class="sg-color-rectangle"
						style="background-color: var(--cr-support-info-bg);"
					></div>
					<div class="sg-color-info">
						<div class="sg-color-name">Info Background</div>
						<div class="sg-color-value">--cr-support-info-bg</div>
					</div>
				</div>
				<div class="sg-color-swatch">
					<div
						class="sg-color-rectangle"
						style="background-color: var(--cr-support-info-fg);"
					></div>
					<div class="sg-color-info">
						<div class="sg-color-name">Info Foreground</div>
						<div class="sg-color-value">--cr-support-info-fg</div>
					</div>
				</div>
			</div>
		</section>
	</div>
</Story>

<style>
	/* Styles are imported from design-tokens.css and style-guide.css */
</style>
