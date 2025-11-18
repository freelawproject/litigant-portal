<script module>
	import { defineMeta } from '@storybook/addon-svelte-csf';
	import {
		Search,
		Scale,
		ChevronDown,
		Smartphone,
		Mail,
		User,
		FileText,
		AlertCircle,
		CheckCircle,
		Info,
		Home,
		Menu
	} from '@lucide/svelte';

	const { Story } = defineMeta({
		title: 'Atoms/Icons',
		tags: ['autodocs'],
		parameters: {
			docs: {
				description: {
					component:
						'Icons from Lucide icon library. Import icons directly from `@lucide/svelte` and use them as components. All icons support `size`, `color`, and `strokeWidth` props. See https://lucide.dev for all available icons.'
				}
			}
		}
	});
</script>

<Story name="Search">
	<Search size={24} />
</Story>

<Story name="Scale">
	<Scale size={24} />
</Story>

<Story name="ChevronDown">
	<ChevronDown size={24} />
</Story>

<Story name="Smartphone">
	<Smartphone size={24} />
</Story>

<Story name="Sizes">
	<div style="display: flex; gap: var(--cr-space-xl); align-items: center;">
		<div style="text-align: center;">
			<Scale size={16} />
			<div class="cr-body-xs" style="margin-top: var(--cr-space-2);">16px</div>
		</div>
		<div style="text-align: center;">
			<Scale size={20} />
			<div class="cr-body-xs" style="margin-top: var(--cr-space-2);">20px</div>
		</div>
		<div style="text-align: center;">
			<Scale size={24} />
			<div class="cr-body-xs" style="margin-top: var(--cr-space-2);">24px</div>
		</div>
		<div style="text-align: center;">
			<Scale size={32} />
			<div class="cr-body-xs" style="margin-top: var(--cr-space-2);">32px</div>
		</div>
		<div style="text-align: center;">
			<Scale size={48} />
			<div class="cr-body-xs" style="margin-top: var(--cr-space-2);">48px</div>
		</div>
	</div>
</Story>

<Story name="Colors">
	<div style="display: flex; gap: var(--cr-space-xl); align-items: center;">
		<div style="text-align: center;">
			<ChevronDown size={32} color="var(--cr-primary-500)" />
			<div class="cr-body-xs" style="margin-top: var(--cr-space-2);">Primary</div>
		</div>
		<div style="text-align: center;">
			<ChevronDown size={32} color="var(--cr-secondary-500)" />
			<div class="cr-body-xs" style="margin-top: var(--cr-space-2);">Secondary</div>
		</div>
		<div style="text-align: center;">
			<ChevronDown size={32} color="var(--cr-default-700)" />
			<div class="cr-body-xs" style="margin-top: var(--cr-space-2);">Neutral</div>
		</div>
	</div>
</Story>

<Story name="Stroke Width">
	<div style="display: flex; gap: var(--cr-space-xl); align-items: center;">
		<div style="text-align: center;">
			<Search size={48} strokeWidth={1} />
			<div class="cr-body-xs" style="margin-top: var(--cr-space-2);">Stroke: 1</div>
		</div>
		<div style="text-align: center;">
			<Search size={48} strokeWidth={2} />
			<div class="cr-body-xs" style="margin-top: var(--cr-space-2);">Stroke: 2</div>
		</div>
		<div style="text-align: center;">
			<Search size={48} strokeWidth={3} />
			<div class="cr-body-xs" style="margin-top: var(--cr-space-2);">Stroke: 3</div>
		</div>
	</div>
</Story>

<Story name="Common Icons Gallery">
	<div
		style="display: grid; grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); gap: var(--cr-space-lg);"
	>
		<div style="text-align: center;">
			<Search size={32} />
			<div class="cr-body-xs" style="margin-top: var(--cr-space-2);">Search</div>
		</div>
		<div style="text-align: center;">
			<Scale size={32} />
			<div class="cr-body-xs" style="margin-top: var(--cr-space-2);">Scale</div>
		</div>
		<div style="text-align: center;">
			<ChevronDown size={32} />
			<div class="cr-body-xs" style="margin-top: var(--cr-space-2);">ChevronDown</div>
		</div>
		<div style="text-align: center;">
			<Smartphone size={32} />
			<div class="cr-body-xs" style="margin-top: var(--cr-space-2);">Smartphone</div>
		</div>
		<div style="text-align: center;">
			<Mail size={32} />
			<div class="cr-body-xs" style="margin-top: var(--cr-space-2);">Mail</div>
		</div>
		<div style="text-align: center;">
			<User size={32} />
			<div class="cr-body-xs" style="margin-top: var(--cr-space-2);">User</div>
		</div>
		<div style="text-align: center;">
			<FileText size={32} />
			<div class="cr-body-xs" style="margin-top: var(--cr-space-2);">FileText</div>
		</div>
		<div style="text-align: center;">
			<AlertCircle size={32} />
			<div class="cr-body-xs" style="margin-top: var(--cr-space-2);">AlertCircle</div>
		</div>
		<div style="text-align: center;">
			<CheckCircle size={32} />
			<div class="cr-body-xs" style="margin-top: var(--cr-space-2);">CheckCircle</div>
		</div>
		<div style="text-align: center;">
			<Info size={32} />
			<div class="cr-body-xs" style="margin-top: var(--cr-space-2);">Info</div>
		</div>
		<div style="text-align: center;">
			<Home size={32} />
			<div class="cr-body-xs" style="margin-top: var(--cr-space-2);">Home</div>
		</div>
		<div style="text-align: center;">
			<Menu size={32} />
			<div class="cr-body-xs" style="margin-top: var(--cr-space-2);">Menu</div>
		</div>
	</div>
</Story>

<Story name="Usage Example">
	<div style="display: flex; flex-direction: column; gap: var(--cr-space-md); max-width: 400px;">
		<div class="cr-body-reg">
			Import icons from <code>@lucide/svelte</code>:
		</div>
		<pre
			style="background: var(--cr-default-100); padding: var(--cr-space-md); border-radius: 4px; overflow-x: auto;"><code
				>import &#123; Search, ChevronDown &#125; from '@lucide/svelte';</code
			></pre>

		<div class="cr-body-reg">Use them as components:</div>
		<pre
			style="background: var(--cr-default-100); padding: var(--cr-space-md); border-radius: 4px; overflow-x: auto;"><code
				>&lt;Search size=&#123;24&#125; /&gt;
&lt;ChevronDown size=&#123;32&#125; color="var(--cr-primary-500)" /&gt;</code
			></pre>

		<div class="cr-body-reg">Example with decorative icon:</div>
		<div style="display: flex; gap: var(--cr-space-sm); align-items: center;">
			<Smartphone size={20} />
			<span class="cr-body-reg">Try the mobile version</span>
		</div>
	</div>
</Story>
