<script module>
	import { defineMeta } from '@storybook/addon-svelte-csf';

	const { Story } = defineMeta({
		title: 'Style Guide/Texture',
		parameters: {
			layout: 'fullscreen',
			docs: {
				description: {
					component:
						'Background texture system with natural, rice, and dust patterns applied over brand colors'
				}
			}
		},
		tags: ['autodocs']
	});
</script>

<Story name="Documentation">
	<div class="sg-section">
		<h2>Background Textures</h2>

		<!-- Texture Introduction -->
		<div class="sg-card sg-margin-bottom-lg">
			<h3>Texture System Overview</h3>
			<div class="sg-card-content">
				<p class="cr-body-reg sg-margin-bottom">
					Three distinct texture overlays add visual depth and tactile quality to backgrounds. Each
					texture can be applied over any brand color to create rich, layered surfaces.
				</p>
				<p class="cr-body-reg">
					<strong>Textures Available:</strong> Natural (organic paper texture), Rice (subtle grain),
					Dust (fine particles)
				</p>
			</div>
		</div>

		<!-- Natural Texture -->
		<section class="sg-texture-group">
			<h3>Natural Texture</h3>
			<div class="sg-texture-swatches">
				<!-- Primary colors -->
				<div class="sg-texture-swatch">
					<div class="sg-texture-rectangle cr-bg-textured cr-bg-natural-p900"></div>
					<div class="sg-texture-info">
						<div class="sg-texture-name">Natural P900</div>
						<div class="sg-texture-value">cr-bg-natural-p900</div>
					</div>
				</div>

				<div class="sg-texture-swatch">
					<div class="sg-texture-rectangle cr-bg-textured cr-bg-natural-p100"></div>
					<div class="sg-texture-info">
						<div class="sg-texture-name">Natural P100</div>
						<div class="sg-texture-value">cr-bg-natural-p100</div>
					</div>
				</div>

				<!-- Secondary colors -->
				<div class="sg-texture-swatch">
					<div class="sg-texture-rectangle cr-bg-textured cr-bg-natural-s900"></div>
					<div class="sg-texture-info">
						<div class="sg-texture-name">Natural S900</div>
						<div class="sg-texture-value">cr-bg-natural-s900</div>
					</div>
				</div>

				<div class="sg-texture-swatch">
					<div class="sg-texture-rectangle cr-bg-textured cr-bg-natural-s100"></div>
					<div class="sg-texture-info">
						<div class="sg-texture-name">Natural S100</div>
						<div class="sg-texture-value">cr-bg-natural-s100</div>
					</div>
				</div>

				<!-- Accent colors -->
				<div class="sg-texture-swatch">
					<div class="sg-texture-rectangle cr-bg-textured cr-bg-natural-a800"></div>
					<div class="sg-texture-info">
						<div class="sg-texture-name">Natural A800</div>
						<div class="sg-texture-value">cr-bg-natural-a800</div>
					</div>
				</div>

				<div class="sg-texture-swatch">
					<div class="sg-texture-rectangle cr-bg-textured cr-bg-natural-a500"></div>
					<div class="sg-texture-info">
						<div class="sg-texture-name">Natural A500</div>
						<div class="sg-texture-value">cr-bg-natural-a500</div>
					</div>
				</div>

				<!-- Default colors -->
				<div class="sg-texture-swatch">
					<div class="sg-texture-rectangle cr-bg-textured cr-bg-natural-d900"></div>
					<div class="sg-texture-info">
						<div class="sg-texture-name">Natural D900</div>
						<div class="sg-texture-value">cr-bg-natural-d900</div>
					</div>
				</div>

				<div class="sg-texture-swatch">
					<div class="sg-texture-rectangle cr-bg-textured cr-bg-natural-d100"></div>
					<div class="sg-texture-info">
						<div class="sg-texture-name">Natural D100</div>
						<div class="sg-texture-value">cr-bg-natural-d100</div>
					</div>
				</div>

				<!-- Surface colors -->
				<div class="sg-texture-swatch">
					<div class="sg-texture-rectangle cr-bg-textured cr-bg-natural-dark"></div>
					<div class="sg-texture-info">
						<div class="sg-texture-name">Natural Dark</div>
						<div class="sg-texture-value">cr-bg-natural-dark</div>
					</div>
				</div>

				<div class="sg-texture-swatch">
					<div class="sg-texture-rectangle cr-bg-textured cr-bg-natural-light"></div>
					<div class="sg-texture-info">
						<div class="sg-texture-name">Natural Light</div>
						<div class="sg-texture-value">cr-bg-natural-light</div>
					</div>
				</div>
			</div>
		</section>

		<!-- Rice Texture -->
		<section class="sg-texture-group">
			<h3>Rice Texture</h3>
			<p class="cr-body-sm sg-margin-bottom" style="color: var(--cr-default-700);">
				Subtle grain texture available in limited palette
			</p>
			<div class="sg-texture-swatches">
				<div class="sg-texture-swatch">
					<div class="sg-texture-rectangle cr-bg-textured cr-bg-rice-d900"></div>
					<div class="sg-texture-info">
						<div class="sg-texture-name">Rice D900</div>
						<div class="sg-texture-value">cr-bg-rice-d900</div>
					</div>
				</div>

				<div class="sg-texture-swatch">
					<div class="sg-texture-rectangle cr-bg-textured cr-bg-rice-d100"></div>
					<div class="sg-texture-info">
						<div class="sg-texture-name">Rice D100</div>
						<div class="sg-texture-value">cr-bg-rice-d100</div>
					</div>
				</div>
			</div>
		</section>

		<!-- Dust Texture -->
		<section class="sg-texture-group">
			<h3>Dust Texture</h3>
			<p class="cr-body-sm sg-margin-bottom" style="color: var(--cr-default-700);">
				Fine particle texture available in limited palette
			</p>
			<div class="sg-texture-swatches">
				<div class="sg-texture-swatch">
					<div class="sg-texture-rectangle cr-bg-textured cr-bg-dust-d900"></div>
					<div class="sg-texture-info">
						<div class="sg-texture-name">Dust D900</div>
						<div class="sg-texture-value">cr-bg-dust-d900</div>
					</div>
				</div>

				<div class="sg-texture-swatch">
					<div class="sg-texture-rectangle cr-bg-textured cr-bg-dust-d300"></div>
					<div class="sg-texture-info">
						<div class="sg-texture-name">Dust D300</div>
						<div class="sg-texture-value">cr-bg-dust-d300</div>
					</div>
				</div>

				<div class="sg-texture-swatch">
					<div class="sg-texture-rectangle cr-bg-textured cr-bg-dust-d100"></div>
					<div class="sg-texture-info">
						<div class="sg-texture-name">Dust D100</div>
						<div class="sg-texture-value">cr-bg-dust-d100</div>
					</div>
				</div>
			</div>
		</section>

		<!-- Usage Guidelines -->
		<div class="sg-card sg-margin-top-lg">
			<h2>Texture Usage Guidelines</h2>
			<div class="sg-card-content">
				<div class="sg-component-grid">
					<div>
						<div class="cr-body-reg sg-margin-bottom">
							<strong>Natural Texture:</strong> Primary texture for hero sections, cards, and large background
							areas. Works well with all brand colors.
						</div>

						<div class="cr-body-reg sg-margin-bottom">
							<strong>Rice Texture:</strong> Subtle texture for secondary backgrounds and supporting
							elements. Use sparingly for minimal visual noise.
						</div>

						<div class="cr-body-reg">
							<strong>Dust Texture:</strong> Ultra-subtle texture for very light backgrounds or sections
							requiring minimal visual distraction.
						</div>
					</div>

					<div>
						<div class="cr-body-reg sg-margin-bottom">
							<strong>Class Combination:</strong> Always use cr-bg-textured as the base class, then add
							the specific texture class (e.g., cr-bg-natural-p900).
						</div>

						<div class="cr-body-reg sg-margin-bottom">
							<strong>Readability:</strong> Ensure sufficient contrast between textured backgrounds and
							text content.
						</div>

						<div class="cr-body-reg">
							<strong>Dark Mode:</strong> Note that accent textures don't toggle in dark mode - they
							maintain their color for brand consistency.
						</div>
					</div>
				</div>

				<div class="sg-tip-box sg-margin-top-lg">
					<div class="cr-body-sm sg-tip-text">
						<strong>Implementation Note:</strong> Texture backgrounds use CSS background images from
						transparenttextures.com. These are applied via CSS classes in your main stylesheet. The textures
						are lightweight and optimized for web performance.
					</div>
				</div>
			</div>
		</div>

		<!-- Code Example -->
		<div class="sg-card sg-margin-top-lg">
			<h2>Code Example</h2>
			<div class="sg-code-box">
				<pre style="margin: 0; color: var(--cr-paper); line-height: 1.6;">
{`<!-- Apply texture to an element -->
<div class="cr-bg-textured cr-bg-natural-p900">
  <h1>Textured Background</h1>
  <p>Content with natural texture overlay</p>
</div>

<!-- Use with card components -->
<section class="hero cr-bg-textured cr-bg-natural-s100">
  <div class="hero-content">
    <!-- Your content here -->
  </div>
</section>`}
				</pre>
			</div>
		</div>
	</div>
</Story>

<style>
	/* Placeholder texture classes - replace with actual texture images */
	.cr-bg-textured {
		position: relative;
	}

	/* Natural Texture Placeholders */
	.cr-bg-natural-p900 {
		background-color: var(--cr-primary-900);
	}
	.cr-bg-natural-p100 {
		background-color: var(--cr-primary-100);
	}
	.cr-bg-natural-s900 {
		background-color: var(--cr-secondary-900);
	}
	.cr-bg-natural-s100 {
		background-color: var(--cr-secondary-100);
	}
	.cr-bg-natural-a800 {
		background-color: var(--cr-accent-800);
	}
	.cr-bg-natural-a500 {
		background-color: var(--cr-accent-500);
	}
	.cr-bg-natural-d900 {
		background-color: var(--cr-default-900);
	}
	.cr-bg-natural-d100 {
		background-color: var(--cr-default-100);
	}
	.cr-bg-natural-dark {
		background-color: var(--cr-ink);
	}
	.cr-bg-natural-light {
		background-color: var(--cr-paper);
	}

	/* Rice Texture Placeholders */
	.cr-bg-rice-d900 {
		background-color: var(--cr-default-900);
	}
	.cr-bg-rice-d100 {
		background-color: var(--cr-default-100);
	}

	/* Dust Texture Placeholders */
	.cr-bg-dust-d900 {
		background-color: var(--cr-default-900);
	}
	.cr-bg-dust-d300 {
		background-color: var(--cr-default-300);
	}
	.cr-bg-dust-d100 {
		background-color: var(--cr-default-100);
	}
</style>
