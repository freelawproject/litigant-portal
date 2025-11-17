import type { Preview } from '@storybook/sveltekit';
import 'virtual:uno.css';
import '../src/app.css';
import '../src/styles/design-tokens.css';
import '../src/styles/style-guide.css';

const preview: Preview = {
	parameters: {
		controls: {
			matchers: {
				color: /(background|color)$/i,
				date: /Date$/i
			}
		},
		options: {
			storySort: {
				order: ['Style Guide', 'Atoms', 'Molecules', 'Organisms', 'Templates']
			}
		}
	}
};

export default preview;
