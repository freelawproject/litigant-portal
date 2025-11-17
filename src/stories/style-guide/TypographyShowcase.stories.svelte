<script module>
	import { defineMeta } from '@storybook/addon-svelte-csf';

	const { Story } = defineMeta({
		title: 'Style Guide/Typography',
		parameters: {
			layout: 'fullscreen',
			docs: {
				description: {
					component:
						'Typography system including font families, title hierarchy, body text, navigation, and player text styles'
				}
			}
		},
		tags: ['autodocs']
	});
</script>

<Story name="Documentation">
	<div class="sg-section">
		<div class="sg-component-grid">
			<!-- Font Families -->
			<div class="sg-example-card">
				<h2>Font Families</h2>
				<div class="sg-margin-bottom">
					<div class="sg-font-antonio sg-font-sample">
						<div class="sg-font-info">
							<strong>Antonio</strong> - Display &amp; Headlines
							<a
								href="https://fonts.google.com/specimen/Antonio"
								target="_blank"
								rel="noopener noreferrer"
								class="sg-font-link"
							>
								View on Google Fonts
							</a>
						</div>
					</div>
					<div class="sg-font-roboto-serif sg-font-sample">
						<div class="sg-font-info">
							<strong>Roboto Serif</strong> - Body Text
							<a
								href="https://fonts.google.com/specimen/Roboto+Serif"
								target="_blank"
								rel="noopener noreferrer"
								class="sg-font-link"
							>
								View on Google Fonts
							</a>
						</div>
					</div>
					<div class="sg-font-roboto sg-font-sample">
						<div class="sg-font-info">
							<strong>Roboto</strong> - Navigation &amp; UI
							<a
								href="https://fonts.google.com/specimen/Roboto"
								target="_blank"
								rel="noopener noreferrer"
								class="sg-font-link"
							>
								View on Google Fonts
							</a>
						</div>
					</div>
				</div>
			</div>

			<!-- Title Hierarchy -->
			<div class="sg-example-card">
				<h2>Title Hierarchy</h2>
				<div class="cr-title-2xl sg-font-sample">Title 2XL</div>
				<div class="cr-title-xl sg-font-sample">Title XL</div>
				<div class="cr-title-lg sg-font-sample">Title LG</div>
				<div class="cr-title-md sg-font-sample">Title MD</div>
				<div class="cr-title-sm sg-font-sample">Title SM</div>
				<div class="cr-title-xs sg-font-sample">Title XS</div>
				<div class="cr-title-2xs sg-font-sample">Title 2XS</div>
				<div class="cr-title-eyebrow sg-font-sample">Eyebrow Text</div>
			</div>

			<!-- Body Text -->
			<div class="sg-example-card">
				<h2>Body Text Styles</h2>
				<div class="cr-body-lg sg-font-sample">Body Large</div>
				<div class="cr-body-reg sg-font-sample">Body Regular</div>
				<div class="cr-body-sm sg-font-sample">Body Small</div>
				<div class="cr-body-xs sg-font-sample">Body XS</div>
			</div>

			<!-- Navigation -->
			<div class="sg-example-card">
				<h2>Navigation Styles</h2>
				<div class="cr-nav1 sg-font-sample">Nav Level 1</div>
				<div class="cr-nav2 sg-font-sample">Nav Level 2</div>
				<div class="cr-nav3 sg-font-sample">Nav Level 3</div>
				<div class="cr-nav-support sg-font-sample">Nav Support</div>
			</div>

			<!-- Player Styles -->
			<div class="sg-example-card">
				<h2>Player Text Styles</h2>
				<div class="cr-player-song sg-font-sample">Song Title</div>
				<div class="cr-player-artist sg-font-sample">Artist Name</div>
				<div class="cr-player-album sg-font-sample">Album Name</div>
				<div class="cr-player-label sg-font-sample">Record Label • Label Name</div>
				<div class="cr-player-dj sg-font-sample">DJ: DJ Name</div>
			</div>

			<!-- Typography Usage Guidelines -->
			<div class="sg-example-card">
				<h2 class="sg-card-title">Typography Usage Guidelines</h2>
				<div class="cr-body-reg sg-margin-bottom">
					<strong>Antonio Font:</strong> Used for all headlines, titles, buttons, and display text. Creates
					bold, impactful typography that represents the radio station's energetic personality.
				</div>
				<div class="cr-body-reg sg-margin-bottom">
					<strong>Roboto Serif:</strong> Used for body content, articles, and longer text passages. Provides
					excellent readability while maintaining a slightly editorial feel appropriate for radio content.
				</div>
				<div class="cr-body-reg">
					<strong>Roboto:</strong> Used for navigation, player interface, and UI elements. Clean and
					functional for interface components.
				</div>
			</div>
		</div>
	</div>
</Story>

<style>
	/* Import the chirp-radio style guide CSS classes */
	/* These styles are defined in the main project's CSS */
</style>
