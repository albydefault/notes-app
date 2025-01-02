from pathlib import Path
import logging
from typing import Optional
from jinja2 import Environment, FileSystemLoader

class PromptTemplateHandler:
    def __init__(self, template_dir: Path):
        """Initialize the template handler with a directory of markdown templates."""
        self.template_dir = template_dir
        self.env = Environment(loader=FileSystemLoader(searchpath=template_dir))
        self.templates = {}
        self._load_templates()

    def _load_templates(self):
        """Load all markdown templates from the template directory."""
        try:
            # Ensure directory exists
            self.template_dir.mkdir(parents=True, exist_ok=True)

            # Load all markdown files
            template_files = self.template_dir.glob('*.md')
            for template_file in template_files:
                template_name = template_file.stem
                self.templates[template_name] = self.env.get_template(f"{template_name}.md")
                logging.info(f"Loaded template: {template_name}")

        except Exception as e:
            logging.error(f"Error loading templates: {str(e)}")
            raise

    def get_template(self, template_name: str) -> Optional[str]:
        """Get a specific template by name."""
        template = self.templates.get(template_name)
        if template is None:
            logging.warning(f"Template not found: {template_name}")
        return template

    def format_template(self, template_name: str, **kwargs) -> str:
        """
        Get and format a template with the provided kwargs.

        Args:
            template_name: Name of the template file (without .md extension)
            **kwargs: Keyword arguments to format the template with

        Returns:
            Formatted template string

        Raises:
            ValueError: If template not found or formatting fails
        """
        template = self.get_template(template_name)
        if not template:
            raise ValueError(f"Template '{template_name}' not found")

        try:
            # Log the variables we're trying to use
            logging.debug(f"Formatting {template_name}")

            # Render the template with Jinja2
            return template.render(**kwargs)

        except Exception as e:
            logging.error(f"Error formatting template {template_name}: {str(e)}")
            raise ValueError(f"Failed to format template '{template_name}': {str(e)}")