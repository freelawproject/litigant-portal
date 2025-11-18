<script module>
	import { defineMeta } from '@storybook/addon-svelte-csf';
	import Input from './Input.svelte';

	const { Story } = defineMeta({
		title: 'Atoms/Input',
		component: Input,
		tags: ['autodocs'],
		argTypes: {
			type: {
				control: { type: 'select' },
				options: ['text', 'email', 'tel', 'url', 'password', 'search'],
				description: 'Input type'
			},
			value: {
				control: 'text',
				description: 'Input value'
			},
			placeholder: {
				control: 'text',
				description: 'Placeholder text'
			},
			disabled: {
				control: 'boolean',
				description: 'Disabled state'
			},
			readonly: {
				control: 'boolean',
				description: 'Readonly state'
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
						'Accessible input component with support for multiple types and states. Meets WCAG 2.1 AA standards with minimum 44px touch targets, proper focus indicators, and high contrast mode support.'
				}
			}
		}
	});
</script>

<Story
	name="Default"
	args={{
		type: 'text',
		placeholder: 'Enter text',
		ariaLabel: 'Text input'
	}}
/>

<Story
	name="With Value"
	args={{
		type: 'text',
		value: 'Sample text',
		placeholder: 'Enter text',
		ariaLabel: 'Text input with value'
	}}
/>

<Story
	name="Email Input"
	args={{
		type: 'email',
		placeholder: 'your@email.com',
		ariaLabel: 'Email address'
	}}
/>

<Story
	name="Telephone Input"
	args={{
		type: 'tel',
		placeholder: '(555) 123-4567',
		ariaLabel: 'Phone number'
	}}
/>

<Story
	name="Search Input"
	args={{
		type: 'search',
		placeholder: 'Search...',
		ariaLabel: 'Search'
	}}
/>

<Story
	name="Password Input"
	args={{
		type: 'password',
		placeholder: 'Enter password',
		ariaLabel: 'Password'
	}}
/>

<Story
	name="Required"
	args={{
		type: 'text',
		placeholder: 'Required field',
		required: true,
		ariaLabel: 'Required text input'
	}}
/>

<Story
	name="Disabled"
	args={{
		type: 'text',
		value: 'Disabled input',
		disabled: true,
		ariaLabel: 'Disabled input'
	}}
/>

<Story
	name="Readonly"
	args={{
		type: 'text',
		value: 'Readonly input',
		readonly: true,
		ariaLabel: 'Readonly input'
	}}
/>

<Story
	name="Error State"
	args={{
		type: 'text',
		value: 'Invalid input',
		error: true,
		ariaLabel: 'Input with error',
		ariaDescribedby: 'error-message'
	}}
>
	<div style="width: 100%; max-width: 400px;">
		<Input
			type="text"
			value="invalid@email"
			error={true}
			placeholder="Enter email"
			ariaLabel="Email input with error"
			ariaDescribedby="error-message"
		/>
		<div
			id="error-message"
			class="cr-body-sm"
			style="color: var(--cr-support-error-fg); margin-top: var(--cr-space-2);"
		>
			Please enter a valid email address
		</div>
	</div>
</Story>

<Story
	name="Success State"
	args={{
		type: 'email',
		value: 'valid@email.com',
		success: true,
		ariaLabel: 'Input with success',
		ariaDescribedby: 'success-message'
	}}
>
	<div style="width: 100%; max-width: 400px;">
		<Input
			type="email"
			value="valid@email.com"
			success={true}
			placeholder="Enter email"
			ariaLabel="Email input with success"
			ariaDescribedby="success-message"
		/>
		<div
			id="success-message"
			class="cr-body-sm"
			style="color: var(--cr-support-success-fg); margin-top: var(--cr-space-2);"
		>
			Email is valid
		</div>
	</div>
</Story>

<Story name="All States">
	<div style="display: flex; flex-direction: column; gap: var(--cr-space-lg); max-width: 400px;">
		<div>
			<label
				for="normal-input"
				class="cr-body-sm"
				style="display: block; margin-bottom: var(--cr-space-2);"
			>
				Normal State
			</label>
			<Input
				id="normal-input"
				type="text"
				placeholder="Enter text"
				ariaLabel="Normal state input"
			/>
		</div>

		<div>
			<label
				for="focused-input"
				class="cr-body-sm"
				style="display: block; margin-bottom: var(--cr-space-2);"
			>
				Focused State (click to focus)
			</label>
			<Input id="focused-input" type="text" placeholder="Click me" ariaLabel="Focusable input" />
		</div>

		<div>
			<label
				for="disabled-input"
				class="cr-body-sm"
				style="display: block; margin-bottom: var(--cr-space-2);"
			>
				Disabled State
			</label>
			<Input
				id="disabled-input"
				type="text"
				value="Disabled"
				disabled={true}
				ariaLabel="Disabled input"
			/>
		</div>

		<div>
			<label
				for="readonly-input"
				class="cr-body-sm"
				style="display: block; margin-bottom: var(--cr-space-2);"
			>
				Readonly State
			</label>
			<Input
				id="readonly-input"
				type="text"
				value="Readonly"
				readonly={true}
				ariaLabel="Readonly input"
			/>
		</div>

		<div>
			<label
				for="error-input"
				class="cr-body-sm"
				style="display: block; margin-bottom: var(--cr-space-2);"
			>
				Error State
			</label>
			<Input
				id="error-input"
				type="text"
				value="Error"
				error={true}
				ariaLabel="Error state input"
				ariaDescribedby="error-msg"
			/>
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
				for="success-input"
				class="cr-body-sm"
				style="display: block; margin-bottom: var(--cr-space-2);"
			>
				Success State
			</label>
			<Input
				id="success-input"
				type="text"
				value="Success"
				success={true}
				ariaLabel="Success state input"
				ariaDescribedby="success-msg"
			/>
			<div
				id="success-msg"
				class="cr-body-xs"
				style="color: var(--cr-support-success-fg); margin-top: var(--cr-space-1);"
			>
				This field is valid
			</div>
		</div>
	</div>
</Story>
