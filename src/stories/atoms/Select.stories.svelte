<script module>
	import { defineMeta } from '@storybook/addon-svelte-csf';
	import Select from './Select.svelte';

	const { Story } = defineMeta({
		title: 'Atoms/Select',
		component: Select,
		tags: ['autodocs'],
		argTypes: {
			value: {
				control: 'text',
				description: 'Selected value'
			},
			disabled: {
				control: 'boolean',
				description: 'Disabled state'
			},
			required: {
				control: 'boolean',
				description: 'Required field'
			},
			error: {
				control: 'boolean',
				description: 'Error state'
			},
			success: {
				control: 'boolean',
				description: 'Success state'
			},
			ariaLabel: {
				control: 'text',
				description: 'Accessible label for screen readers'
			}
		},
		parameters: {
			docs: {
				description: {
					component:
						'Accessible select/dropdown component with custom styling and Lucide chevron icon. Supports multiple states and meets WCAG 2.1 AA standards with minimum 44px touch targets and proper focus indicators.'
				}
			}
		}
	});
</script>

<Story name="Default">
	<Select ariaLabel="Select an option">
		<option value="">Select an option</option>
		<option value="option1">Option 1</option>
		<option value="option2">Option 2</option>
		<option value="option3">Option 3</option>
	</Select>
</Story>

<Story name="With Value">
	<Select value="option2" ariaLabel="Select with value">
		<option value="">Select an option</option>
		<option value="option1">Option 1</option>
		<option value="option2">Option 2</option>
		<option value="option3">Option 3</option>
	</Select>
</Story>

<Story name="Required">
	<Select required={true} ariaLabel="Required select">
		<option value="">Select an option</option>
		<option value="option1">Option 1</option>
		<option value="option2">Option 2</option>
	</Select>
</Story>

<Story name="Disabled">
	<Select disabled={true} ariaLabel="Disabled select">
		<option value="">Select an option</option>
		<option value="option1">Option 1</option>
		<option value="option2">Option 2</option>
	</Select>
</Story>

<Story name="Error State">
	<div style="width: 100%; max-width: 400px;">
		<Select error={true} ariaLabel="Select with error" ariaDescribedby="error-message">
			<option value="">Select an option</option>
			<option value="option1">Option 1</option>
			<option value="option2">Option 2</option>
		</Select>
		<div
			id="error-message"
			class="cr-body-sm"
			style="color: var(--cr-support-error-fg); margin-top: var(--cr-space-2);"
		>
			Please select a valid option
		</div>
	</div>
</Story>

<Story name="Success State">
	<div style="width: 100%; max-width: 400px;">
		<Select
			value="option1"
			success={true}
			ariaLabel="Select with success"
			ariaDescribedby="success-message"
		>
			<option value="">Select an option</option>
			<option value="option1">Option 1</option>
			<option value="option2">Option 2</option>
		</Select>
		<div
			id="success-message"
			class="cr-body-sm"
			style="color: var(--cr-support-success-fg); margin-top: var(--cr-space-2);"
		>
			Valid selection
		</div>
	</div>
</Story>

<Story name="All States">
	<div style="display: flex; flex-direction: column; gap: var(--cr-space-lg); max-width: 400px;">
		<div>
			<label
				for="normal-select"
				class="cr-body-sm"
				style="display: block; margin-bottom: var(--cr-space-2);"
			>
				Normal State
			</label>
			<Select id="normal-select" ariaLabel="Normal select">
				<option value="">Select an option</option>
				<option value="option1">Option 1</option>
				<option value="option2">Option 2</option>
			</Select>
		</div>

		<div>
			<label
				for="disabled-select"
				class="cr-body-sm"
				style="display: block; margin-bottom: var(--cr-space-2);"
			>
				Disabled State
			</label>
			<Select id="disabled-select" disabled={true} ariaLabel="Disabled select">
				<option value="">Select an option</option>
				<option value="option1">Option 1</option>
			</Select>
		</div>

		<div>
			<label
				for="error-select"
				class="cr-body-sm"
				style="display: block; margin-bottom: var(--cr-space-2);"
			>
				Error State
			</label>
			<Select id="error-select" error={true} ariaLabel="Error select" ariaDescribedby="error-msg">
				<option value="">Select an option</option>
				<option value="option1">Option 1</option>
			</Select>
			<div
				id="error-msg"
				class="cr-body-xs"
				style="color: var(--cr-support-error-fg); margin-top: var(--cr-space-1);"
			>
				This field has an error
			</div>
		</div>

		<div>
			<label
				for="success-select"
				class="cr-body-sm"
				style="display: block; margin-bottom: var(--cr-space-2);"
			>
				Success State
			</label>
			<Select
				id="success-select"
				value="option1"
				success={true}
				ariaLabel="Success select"
				ariaDescribedby="success-msg"
			>
				<option value="">Select an option</option>
				<option value="option1">Option 1</option>
			</Select>
			<div
				id="success-msg"
				class="cr-body-xs"
				style="color: var(--cr-support-success-fg); margin-top: var(--cr-space-1);"
			>
				Valid selection
			</div>
		</div>
	</div>
</Story>

<Story name="Real World Examples">
	<div style="display: flex; flex-direction: column; gap: var(--cr-space-lg); max-width: 400px;">
		<div>
			<label
				for="court-select"
				class="cr-body-sm"
				style="display: block; margin-bottom: var(--cr-space-2);"
			>
				How to represent yourself in court
			</label>
			<Select id="court-select" ariaLabel="How to represent yourself in court">
				<option value="">Choose a topic</option>
				<option value="preparation">Preparation tips</option>
				<option value="documents">Required documents</option>
				<option value="procedures">Court procedures</option>
				<option value="rights">Your rights</option>
			</Select>
		</div>

		<div>
			<label
				for="case-select"
				class="cr-body-sm"
				style="display: block; margin-bottom: var(--cr-space-2);"
			>
				Next steps in your case
			</label>
			<Select id="case-select" ariaLabel="Next steps in your case">
				<option value="">Select a step</option>
				<option value="filing">File initial paperwork</option>
				<option value="service">Serve the other party</option>
				<option value="response">Wait for response</option>
				<option value="hearing">Attend hearing</option>
			</Select>
		</div>

		<div>
			<label
				for="state-select"
				class="cr-body-sm"
				style="display: block; margin-bottom: var(--cr-space-2);"
			>
				State
			</label>
			<Select id="state-select" ariaLabel="Select state">
				<option value="">Select state</option>
				<option value="IL">Illinois</option>
				<option value="IN">Indiana</option>
				<option value="WI">Wisconsin</option>
				<option value="MI">Michigan</option>
			</Select>
		</div>
	</div>
</Story>
