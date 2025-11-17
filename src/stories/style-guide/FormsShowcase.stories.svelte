<script module>
	import { defineMeta } from '@storybook/addon-svelte-csf';

	const { Story } = defineMeta({
		title: 'Style Guide/Forms',
		parameters: {
			layout: 'fullscreen',
			docs: {
				description: {
					component: 'Form element styles, input patterns, validation states, and layout guidelines'
				}
			}
		},
		tags: ['autodocs']
	});
</script>

<Story name="Documentation">
	<div style="padding: var(--cr-space-6); background: var(--cr-background); min-height: 100vh;">
		<!-- Header -->
		<div
			style="text-align: center; margin-bottom: var(--cr-space-8); border-bottom: 1px solid var(--cr-default-300); padding-bottom: var(--cr-space-6);"
		>
			<h1 style="font: var(--cr-title-xl); color: var(--cr-ink); margin: 0 0 var(--cr-space-4) 0;">
				Forms Documentation
			</h1>
			<p
				style="font: var(--cr-body-reg); color: var(--cr-default-700); max-width: 600px; margin: 0 auto;"
			>
				Complete documentation of form elements, input styles, and layout patterns used across the
				application.
			</p>
		</div>

		<!-- Global Form Elements -->
		<div style="margin-bottom: var(--cr-space-8);">
			<h2 style="font: var(--cr-title-lg); color: var(--cr-ink); margin-bottom: var(--cr-space-6);">
				Global Form Elements
			</h2>

			<div
				style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: var(--cr-space-6);"
			>
				<!-- Basic Inputs -->
				<div
					style="padding: var(--cr-space-5); border: 1px solid var(--cr-default-300); border-radius: var(--cr-space-2);"
				>
					<h3 style="font: var(--cr-nav2); color: var(--cr-ink); margin-bottom: var(--cr-space-4);">
						Basic Input Elements
					</h3>

					<div style="display: flex; flex-direction: column; gap: var(--cr-space-5);">
						<div class="form-group">
							<label class="form-label">Text Input</label>
							<input type="text" placeholder="Enter text" value="Sample text" readonly />
						</div>

						<div class="form-group">
							<label class="form-label">Email Input</label>
							<input type="email" placeholder="your@email.com" value="user@example.com" readonly />
						</div>

						<div class="form-group">
							<label class="form-label">Phone Input</label>
							<input type="tel" placeholder="(555) 123-4567" value="(555) 123-4567" readonly />
						</div>

						<div class="form-group">
							<label class="form-label">Select Dropdown</label>
							<select disabled>
								<option value="mobile">Mobile</option>
								<option value="home">Home</option>
								<option value="work">Work</option>
							</select>
						</div>

						<div class="form-group">
							<label class="form-label">Textarea</label>
							<textarea rows="3" placeholder="Enter description..." readonly
								>Sample textarea content</textarea
							>
						</div>
					</div>
				</div>

				<!-- Input States -->
				<div
					style="padding: var(--cr-space-5); border: 1px solid var(--cr-default-300); border-radius: var(--cr-space-2);"
				>
					<h3 style="font: var(--cr-nav2); color: var(--cr-ink); margin-bottom: var(--cr-space-4);">
						Input States
					</h3>

					<div style="display: flex; flex-direction: column; gap: var(--cr-space-5);">
						<div class="form-group">
							<label class="form-label">Normal State</label>
							<input type="text" placeholder="Enter text" value="Normal input" readonly />
						</div>

						<div class="form-group">
							<label class="form-label">Focused State (hover to see)</label>
							<input type="text" placeholder="Focus me" value="Focused input" />
						</div>

						<div class="form-group">
							<label class="form-label">Disabled State</label>
							<input type="text" placeholder="Disabled" value="Disabled input" disabled />
						</div>

						<div class="form-group">
							<label class="form-label">Readonly State</label>
							<input type="text" placeholder="Readonly" value="Readonly input" readonly />
						</div>

						<div class="form-group">
							<label class="form-label">Success State</label>
							<input
								type="text"
								placeholder="Valid input"
								value="✓ Valid email"
								style="border-color: var(--cr-support-success-fg);"
								readonly
							/>
						</div>

						<div class="form-group">
							<label class="form-label">Error State</label>
							<input
								type="text"
								placeholder="Invalid input"
								value="Invalid email"
								style="border-color: var(--cr-support-error-fg);"
								readonly
							/>
							<div
								style="font: var(--cr-body-xs); color: var(--cr-support-error-fg); margin-top: var(--cr-space-1);"
							>
								Please enter a valid email address
							</div>
						</div>
					</div>
				</div>
			</div>
		</div>

		<!-- Form Layout Patterns -->
		<div style="margin-bottom: var(--cr-space-8);">
			<h2 style="font: var(--cr-title-lg); color: var(--cr-ink); margin-bottom: var(--cr-space-6);">
				Form Layout Patterns
			</h2>

			<div
				style="padding: var(--cr-space-5); border: 1px solid var(--cr-default-300); border-radius: var(--cr-space-2);"
			>
				<h3 style="font: var(--cr-nav2); color: var(--cr-ink); margin-bottom: var(--cr-space-4);">
					Two-Column Layout
				</h3>

				<div
					style="display: grid; grid-template-columns: 1fr 1fr; gap: var(--cr-space-4); margin-bottom: var(--cr-space-4);"
				>
					<div class="form-group">
						<label class="form-label">First Name</label>
						<input type="text" placeholder="First name" value="John" readonly />
					</div>

					<div class="form-group">
						<label class="form-label">Last Name</label>
						<input type="text" placeholder="Last name" value="Doe" readonly />
					</div>
				</div>

				<div
					style="display: grid; grid-template-columns: 2fr 1fr; gap: var(--cr-space-4); margin-bottom: var(--cr-space-4);"
				>
					<div class="form-group">
						<label class="form-label">City</label>
						<input type="text" placeholder="City" value="Chicago" readonly />
					</div>

					<div class="form-group">
						<label class="form-label">State</label>
						<select disabled>
							<option value="IL">IL</option>
							<option value="NY">NY</option>
							<option value="CA">CA</option>
						</select>
					</div>
				</div>

				<div class="form-group">
					<label class="form-label">Full Width Input</label>
					<input type="text" placeholder="Address line 1" value="123 Main Street" readonly />
				</div>
			</div>
		</div>

		<!-- Checkboxes and Radio Buttons -->
		<div style="margin-bottom: var(--cr-space-8);">
			<h2 style="font: var(--cr-title-lg); color: var(--cr-ink); margin-bottom: var(--cr-space-6);">
				Checkboxes & Radio Buttons
			</h2>

			<div
				style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: var(--cr-space-6);"
			>
				<!-- Checkboxes -->
				<div
					style="padding: var(--cr-space-5); border: 1px solid var(--cr-default-300); border-radius: var(--cr-space-2);"
				>
					<h3 style="font: var(--cr-nav2); color: var(--cr-ink); margin-bottom: var(--cr-space-4);">
						Checkboxes
					</h3>

					<div style="display: flex; flex-direction: column; gap: var(--cr-space-3);">
						<label
							style="display: flex; align-items: center; gap: var(--cr-space-2); cursor: pointer;"
						>
							<input type="checkbox" checked disabled />
							<span style="font: var(--cr-body-reg);">Selected option</span>
						</label>

						<label
							style="display: flex; align-items: center; gap: var(--cr-space-2); cursor: pointer;"
						>
							<input type="checkbox" disabled />
							<span style="font: var(--cr-body-reg);">Unselected option</span>
						</label>

						<label
							style="display: flex; align-items: center; gap: var(--cr-space-2); cursor: pointer;"
						>
							<input type="checkbox" checked disabled />
							<span style="font: var(--cr-body-reg);">Another selected option</span>
						</label>
					</div>
				</div>

				<!-- Radio Buttons -->
				<div
					style="padding: var(--cr-space-5); border: 1px solid var(--cr-default-300); border-radius: var(--cr-space-2);"
				>
					<h3 style="font: var(--cr-nav2); color: var(--cr-ink); margin-bottom: var(--cr-space-4);">
						Radio Buttons
					</h3>

					<div style="display: flex; flex-direction: column; gap: var(--cr-space-3);">
						<label
							style="display: flex; align-items: center; gap: var(--cr-space-2); cursor: pointer;"
						>
							<input type="radio" name="example" checked disabled />
							<span style="font: var(--cr-body-reg);">Option 1 (selected)</span>
						</label>

						<label
							style="display: flex; align-items: center; gap: var(--cr-space-2); cursor: pointer;"
						>
							<input type="radio" name="example" disabled />
							<span style="font: var(--cr-body-reg);">Option 2</span>
						</label>

						<label
							style="display: flex; align-items: center; gap: var(--cr-space-2); cursor: pointer;"
						>
							<input type="radio" name="example" disabled />
							<span style="font: var(--cr-body-reg);">Option 3</span>
						</label>
					</div>
				</div>
			</div>
		</div>

		<!-- Usage Guidelines -->
		<div class="sg-card">
			<h2 style="font: var(--cr-title-lg); color: var(--cr-ink); margin-bottom: var(--cr-space-4);">
				Form Usage Guidelines
			</h2>
			<div class="sg-card-content">
				<div class="sg-component-grid">
					<div>
						<div class="cr-body-reg sg-margin-bottom">
							<strong>Labels:</strong> Always place labels above inputs. Use clear, concise language.
						</div>

						<div class="cr-body-reg sg-margin-bottom">
							<strong>Placeholder Text:</strong> Use for examples or format hints, not as labels.
						</div>

						<div class="cr-body-reg">
							<strong>Required Fields:</strong> Mark with asterisk (*) or "Required" text.
						</div>
					</div>

					<div>
						<div class="cr-body-reg sg-margin-bottom">
							<strong>Validation:</strong> Show errors inline, below the field.
						</div>

						<div class="cr-body-reg sg-margin-bottom">
							<strong>Focus States:</strong> Provide clear visual feedback with border and shadow.
						</div>

						<div class="cr-body-reg">
							<strong>Spacing:</strong> Use 16px (--cr-space-4) between form fields.
						</div>
					</div>
				</div>

				<div class="sg-tip-box sg-margin-top-lg">
					<div class="cr-body-sm sg-tip-text">
						<strong>Accessibility Tip:</strong> Ensure all form fields have associated labels using the
						for/id attributes or by wrapping inputs. Use aria-describedby for error messages.
					</div>
				</div>
			</div>
		</div>
	</div>
</Story>

<style>
	/* Form Styles */
	.form-group {
		display: flex;
		flex-direction: column;
		gap: var(--cr-space-2);
	}

	.form-label {
		font: var(--cr-nav-support);
		color: var(--cr-ink);
		font-weight: 500;
	}

	input[type='text'],
	input[type='email'],
	input[type='tel'],
	input[type='password'],
	input[type='url'],
	select,
	textarea {
		font: var(--cr-body-reg);
		padding: var(--cr-space-2) var(--cr-space-3);
		border: 1px solid var(--cr-default-300);
		border-radius: var(--cr-space-1);
		background-color: var(--cr-paper);
		color: var(--cr-ink);
		transition: all 0.2s ease;
	}

	input:focus,
	select:focus,
	textarea:focus {
		outline: none;
		border-color: var(--cr-primary-500);
		box-shadow: 0 0 0 3px var(--cr-primary-100);
	}

	input:disabled,
	select:disabled,
	textarea:disabled {
		background-color: var(--cr-default-100);
		color: var(--cr-default-500);
		cursor: not-allowed;
	}

	input[readonly],
	textarea[readonly] {
		background-color: var(--cr-default-100);
		cursor: default;
	}

	textarea {
		resize: vertical;
		min-height: 80px;
	}

	input[type='checkbox'],
	input[type='radio'] {
		width: 18px;
		height: 18px;
		cursor: pointer;
	}
</style>
