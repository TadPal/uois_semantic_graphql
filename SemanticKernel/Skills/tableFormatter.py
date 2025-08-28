import json
from typing import Annotated
from semantic_kernel.functions import kernel_function
from semantic_kernel.functions import KernelArguments


class TableFormatterPlugin:
    @kernel_function(
        name="jsonToMarkdownTable",
        # description="Formats a list of dictionaries (JSON string) into a Markdown table.",
    )
    async def format_as_table(
        self,
        json_data: Annotated[
            str, "A JSON string representing a list of objects (dictionaries)."
        ],
        arguments: KernelArguments = None,
    ) -> str:
        """
        Converts JSON data to a formatted Markdown table. Only to be used when specifically asked for a table.

        Args:
          json_data: json list of GQL structures, e.g. ["userPage": [{"id": "51d101a0-81f1-44ca-8366-6cf51432e8d6", "name": "Zdeňka"},{"id": "76dac14f-7114-4bb2-882d-0d762eab6f4a","name": "Estera"}]]

        Returns:
          A markdown formatted string containing the json data formatted into a table.
        """
        try:
            data = json.loads(json_data)
        except json.JSONDecodeError:
            return "Invalid JSON data provided."

        if not isinstance(data, list) or not data:
            return "Data is not a list or is empty."

        headers = set()
        for item in data:
            if isinstance(item, dict):
                headers.update(item.keys())

        headers = sorted(list(headers))
        if not headers:
            return "No data found to create a table."

        markdown_table = "| " + " | ".join(headers) + " |\n"
        markdown_table += "|---" * len(headers) + "|\n"

        for item in data:
            if isinstance(item, dict):
                row_values = []
                for header in headers:
                    value = item.get(header, "")
                    row_values.append(str(value))
                markdown_table += "| " + " | ".join(row_values) + " |\n"

        return markdown_table
