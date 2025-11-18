<script module>
	import { defineMeta } from '@storybook/addon-svelte-csf';
	import Button from './Button.svelte';
	import { Mail, ArrowRight, Plus } from '@lucide/svelte';

	const { Story } = defineMeta({
		title: 'Atoms/Button',
		component: Button,
		tags: ['autodocs'],
		argTypes: {
			variant: {
				control: { type: 'select' },
				options: ['primary', 'secondary', 'tertiary', 'ghost'],
				description: 'Button variant'
			},
			type: {
				control: { type: 'select' },
				options: ['button', 'submit', 'reset'],
				description: 'Button type'
			},
			disabled: {
				control: 'boolean',
				description: 'Disabled state'
			},
			fullWidth: {
				control: 'boolean',
				description: 'Full width button'
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
						'Accessible button component with multiple variants. Meets WCAG 2.1 AA standards with minimum 44px touch targets, proper focus indicators, and high contrast mode support.'
				}
			}
		}
	});
</script>

<Story name="Primary">
	<Button variant="primary">Primary Button</Button>
</Story>

<Story name="Secondary">
	<Button variant="secondary">Secondary Button</Button>
</Story>

<Story name="Tertiary">
	<Button variant="tertiary">Tertiary Button</Button>
</Story>

<Story name="Ghost">
	<Button variant="ghost">Ghost Button</Button>
</Story>

<Story name="Disabled">
	<div style="display: flex; gap: var(--cr-space-4); flex-wrap: wrap;">
		<Button variant="primary" disabled={true}>Primary Disabled</Button>
		<Button variant="secondary" disabled={true}>Secondary Disabled</Button>
		<Button variant="tertiary" disabled={true}>Tertiary Disabled</Button>
		<Button variant="ghost" disabled={true}>Ghost Disabled</Button>
	</div>
</Story>

<Story name="With Icons">
	<div style="display: flex; gap: var(--cr-space-4); flex-wrap: wrap; align-items: center;">
		<Button variant="primary">
			<Mail size={20} />
			Send Email
		</Button>
		<Button variant="secondary">
			Continue
			<ArrowRight size={20} />
		</Button>
		<Button variant="tertiary">
			<Plus size={20} />
			Add Item
		</Button>
	</div>
</Story>

<Story name="Full Width">
	<div style="max-width: 400px;">
		<Button variant="primary" fullWidth={true}>Full Width Button</Button>
	</div>
</Story>

<Story name="All Variants">
	<div style="display: flex; flex-direction: column; gap: var(--cr-space-lg); max-width: 400px;">
		<div>
			<div class="cr-body-sm" style="margin-bottom: var(--cr-space-2); font-weight: 600;">
				Primary Variant
			</div>
			<Button variant="primary">Get Started</Button>
		</div>

		<div>
			<div class="cr-body-sm" style="margin-bottom: var(--cr-space-2); font-weight: 600;">
				Secondary Variant
			</div>
			<Button variant="secondary">Learn More</Button>
		</div>

		<div>
			<div class="cr-body-sm" style="margin-bottom: var(--cr-space-2); font-weight: 600;">
				Tertiary Variant
			</div>
			<Button variant="tertiary">View Details</Button>
		</div>

		<div>
			<div class="cr-body-sm" style="margin-bottom: var(--cr-space-2); font-weight: 600;">
				Ghost Variant
			</div>
			<Button variant="ghost">Cancel</Button>
		</div>

		<div>
			<div class="cr-body-sm" style="margin-bottom: var(--cr-space-2); font-weight: 600;">
				Disabled State
			</div>
			<Button variant="primary" disabled={true}>Disabled Button</Button>
		</div>
	</div>
</Story>

<Story name="Real World Examples">
	<div style="display: flex; flex-direction: column; gap: var(--cr-space-xl); max-width: 500px;">
		<div>
			<h3 class="cr-title-sm" style="margin-bottom: var(--cr-space-3);">Form Actions</h3>
			<div style="display: flex; gap: var(--cr-space-3); justify-content: flex-end;">
				<Button variant="ghost">Cancel</Button>
				<Button variant="primary" type="submit">Submit Form</Button>
			</div>
		</div>

		<div>
			<h3 class="cr-title-sm" style="margin-bottom: var(--cr-space-3);">Call to Action</h3>
			<Button variant="primary" fullWidth={true}>
				File Your Case
				<ArrowRight size={20} />
			</Button>
		</div>

		<div>
			<h3 class="cr-title-sm" style="margin-bottom: var(--cr-space-3);">Button Group</h3>
			<div style="display: flex; gap: var(--cr-space-3); flex-wrap: wrap;">
				<Button variant="tertiary">Back</Button>
				<Button variant="primary">Next Step</Button>
			</div>
		</div>

		<div>
			<h3 class="cr-title-sm" style="margin-bottom: var(--cr-space-3);">Contact Options</h3>
			<div style="display: flex; flex-direction: column; gap: var(--cr-space-3);">
				<Button variant="primary" fullWidth={true}>
					<Mail size={20} />
					Email Support
				</Button>
				<Button variant="secondary" fullWidth={true}>View FAQs</Button>
			</div>
		</div>
	</div>
</Story>
