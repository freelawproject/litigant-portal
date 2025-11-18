<script module>
	import { defineMeta } from '@storybook/addon-svelte-csf';
	import SearchInput from './SearchInput.svelte';

	const { Story } = defineMeta({
		title: 'Molecules/SearchInput',
		component: SearchInput,
		tags: ['autodocs'],
		argTypes: {
			value: {
				control: 'text',
				description: 'Search input value'
			},
			placeholder: {
				control: 'text',
				description: 'Placeholder text'
			},
			disabled: {
				control: 'boolean',
				description: 'Disabled state'
			},
			required: {
				control: 'boolean',
				description: 'Required field'
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
						'Search input molecule combining an input field with a search icon. Meets WCAG 2.1 AA standards with proper focus indicators and accessibility features.'
				}
			}
		}
	});
</script>

<Story name="Default">
	<div style="max-width: 400px;">
		<SearchInput ariaLabel="Search legal topics" placeholder="Search for legal help..." />
	</div>
</Story>

<Story name="With Value">
	<div style="max-width: 400px;">
		<SearchInput
			value="eviction"
			ariaLabel="Search legal topics"
			placeholder="Search for legal help..."
		/>
	</div>
</Story>

<Story name="Disabled">
	<div style="max-width: 400px;">
		<SearchInput
			disabled={true}
			ariaLabel="Search legal topics"
			placeholder="Search for legal help..."
		/>
	</div>
</Story>

<Story name="Required">
	<div style="max-width: 400px;">
		<SearchInput
			required={true}
			ariaLabel="Search legal topics"
			placeholder="Search for legal help..."
		/>
	</div>
</Story>

<Story name="Full Width">
	<SearchInput ariaLabel="Search the site" placeholder="Search..." />
</Story>

<Story name="Real World Examples">
	<div style="display: flex; flex-direction: column; gap: var(--cr-space-xl); max-width: 600px;">
		<div>
			<h3 class="cr-title-sm" style="margin-bottom: var(--cr-space-3);">Homepage Search</h3>
			<SearchInput
				ariaLabel="Search for legal help"
				placeholder="What legal issue do you need help with?"
			/>
		</div>

		<div>
			<h3 class="cr-title-sm" style="margin-bottom: var(--cr-space-3);">Document Search</h3>
			<SearchInput ariaLabel="Search documents" placeholder="Search your documents..." />
		</div>

		<div>
			<h3 class="cr-title-sm" style="margin-bottom: var(--cr-space-3);">Search with Label</h3>
			<label
				for="case-search"
				class="cr-body-sm"
				style="display: block; margin-bottom: var(--cr-space-2);"
			>
				Find Your Case
			</label>
			<SearchInput
				id="case-search"
				ariaLabel="Find your case"
				placeholder="Enter case number or name..."
			/>
		</div>
	</div>
</Story>
