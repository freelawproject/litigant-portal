<script module>
	import { defineMeta } from '@storybook/addon-svelte-csf';
	import CategoryCard from './CategoryCard.svelte';

	const { Story } = defineMeta({
		title: 'Molecules/CategoryCard',
		component: CategoryCard,
		tags: ['autodocs'],
		argTypes: {
			label: {
				control: 'text',
				description: 'Primary label text'
			},
			subtitle: {
				control: 'text',
				description: 'Secondary label/subtitle'
			},
			selected: {
				control: 'boolean',
				description: 'Selected state'
			},
			disabled: {
				control: 'boolean',
				description: 'Disabled state'
			}
		},
		parameters: {
			docs: {
				description: {
					component:
						'Category card molecule - a clickable button for selecting legal issue categories. Two-line design with primary label and subtitle, matching the homepage mockup. Includes hover, focus, selected, and disabled states.'
				}
			}
		}
	});
</script>

<script>
	let selectedCategory = $state('');
</script>

<Story name="Default">
	<CategoryCard label="Unlawful Detainer" subtitle="Eviction" />
</Story>

<Story name="Selected">
	<CategoryCard label="Warrant in Debt" subtitle="Debt Collection" selected={true} />
</Story>

<Story name="Disabled">
	<CategoryCard label="Coming Soon" subtitle="Not available yet" disabled={true} />
</Story>

<Story name="Horizontal Layout">
	<div style="display: flex; gap: var(--cr-space-3); flex-wrap: wrap;">
		<CategoryCard label="Unlawful Detainer" subtitle="Eviction" />
		<CategoryCard label="Warrant in Debt" subtitle="Debt Collection" />
		<CategoryCard label="Tenant's Assertion & Complaint" subtitle="Plain lang. simplification" />
		<CategoryCard label="Protective Orders" subtitle="Plain lang. simplification" />
		<CategoryCard label="Garnishment & Interrogatories" subtitle="Plain lang. simplification" />
	</div>
</Story>

<Story name="Interactive Example">
	<div style="max-width: 800px;">
		<h3 class="cr-title-md" style="margin-bottom: var(--cr-space-4);">
			Select your legal issue or describe your problem
		</h3>
		<div style="display: flex; gap: var(--cr-space-3); flex-wrap: wrap;">
			<CategoryCard
				label="Unlawful Detainer"
				subtitle="Eviction"
				selected={selectedCategory === 'detainer'}
				onclick={() => {
					selectedCategory = 'detainer';
					alert('Unlawful Detainer selected');
				}}
			/>
			<CategoryCard
				label="Warrant in Debt"
				subtitle="Debt Collection"
				selected={selectedCategory === 'warrant'}
				onclick={() => {
					selectedCategory = 'warrant';
					alert('Warrant in Debt selected');
				}}
			/>
			<CategoryCard
				label="Tenant's Assertion & Complaint"
				subtitle="Plain lang. simplification"
				selected={selectedCategory === 'assertion'}
				onclick={() => {
					selectedCategory = 'assertion';
					alert('Tenant Assertion selected');
				}}
			/>
			<CategoryCard
				label="Protective Orders"
				subtitle="Plain lang. simplification"
				selected={selectedCategory === 'protective'}
				onclick={() => {
					selectedCategory = 'protective';
					alert('Protective Orders selected');
				}}
			/>
			<CategoryCard
				label="Garnishment & Interrogatories"
				subtitle="Plain lang. simplification"
				selected={selectedCategory === 'garnishment'}
				onclick={() => {
					selectedCategory = 'garnishment';
					alert('Garnishment selected');
				}}
			/>
		</div>
	</div>
</Story>
