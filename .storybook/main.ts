import type { StorybookConfig } from '@storybook/sveltekit';
import UnoCSS from 'unocss/vite';

const config: StorybookConfig = {
	stories: ['../src/**/*.mdx', '../src/**/*.stories.@(js|ts|svelte)'],
	addons: [
		'@storybook/addon-svelte-csf',
		'@chromatic-com/storybook',
		'@storybook/addon-docs',
		'@storybook/addon-a11y',
		'@storybook/addon-vitest'
	],
	framework: {
		name: '@storybook/sveltekit',
		options: {}
	},
	async viteFinal(config) {
		config.plugins = config.plugins || [];
		config.plugins.push(UnoCSS());
		return config;
	}
};
export default config;
