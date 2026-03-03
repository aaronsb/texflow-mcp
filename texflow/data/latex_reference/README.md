# LaTeX Reference Data

This directory contains reference data for the TeXFlow LaTeX documentation tool.

## Data Sources and Licensing

### Commands and Environments
- **Source**: Derived from common LaTeX2e documentation
- **License**: LaTeX Project Public License (LPPL)
- **Content**: Core LaTeX commands, environments, and sectioning

### Symbols
- **Source**: Common LaTeX symbols from various sources
- **License**: LPPL for LaTeX symbols
- **Content**: Greek letters, mathematical symbols, operators

### Packages
- **Source**: Package documentation summaries
- **License**: Individual package licenses (mostly LPPL)
- **Content**: amsmath and other common packages

### Error Patterns
- **Source**: Common LaTeX error messages and community solutions
- **License**: Public domain / community knowledge
- **Content**: Error patterns with explanations and fixes

## Data Format

All data is stored in JSON format for easy parsing and searching:

```json
{
  "command_name": {
    "syntax": "\\command[options]{arguments}",
    "description": "What the command does",
    "package": "built-in or package-name",
    "category": "category-name",
    "examples": ["example 1", "example 2"],
    "related": ["related-command-1", "related-command-2"]
  }
}
```

## Adding New Data

To add new reference data:

1. Ensure proper licensing (LPPL-compatible or more permissive)
2. Follow the existing JSON structure
3. Include source attribution in metadata.json
4. Test with the reference tool

## Future Enhancements

- Automated extraction from latex2e-help-texinfo
- PDF parsing of Comprehensive LaTeX Symbol List
- Integration with CTAN package documentation
- Visual rendering of symbols