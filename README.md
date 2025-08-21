# KeyTheft - OpenAI API Key Discovery & Validation

A quick and dirty Proof of Concept for discovering and validating OpenAI API keys on GitHub using search sharding techniques to overcome GitHub's API limitations.

## Overview

This toolkit consists of two main components:
1. **GitHub Key Search** (`github_key_search.py`) - Discovers OpenAI API keys from GitHub repositories
2. **API Key Tester** (`tester.py`) - Validates discovered keys against OpenAI's API

## Features

### GitHub Key Search (`github_key_search.py`)
- **Sharded Search Strategy**: Overcomes GitHub's 1000 result limit by using multiple search queries
- **Multiple Search Dimensions**: 
  - Programming languages (Python, JavaScript, TypeScript, etc.)
  - File extensions (.env, .config, .ini, etc.)
  - Logical combinations (python + .py, javascript + .env)
  - Filename patterns (development, production, local)
  - Path-based searches (config/, .github/, docker/)
- **Advanced Pattern Matching**: Regex-based detection of `sk-proj-` format API keys
- **Rate Limit Handling**: Automatic retry logic with exponential backoff
- **Rich Terminal UI**: Professional formatting with progress bars and panels
- **Comprehensive Output**: JSON results, extracted keys, and shard statistics

### API Key Tester (`tester.py`)
- **Batch Testing**: Test multiple keys from a file with configurable limits and delays
- **Smart Error Classification**: Distinguishes between invalid keys and valid keys with other issues
- **OpenAI Error Code Compliance**: Follows official OpenAI error code documentation
- **Rich Progress Tracking**: Real-time progress bars and detailed status reporting
- **Flexible Input**: Test single keys or batch process from files
- **Detailed Results**: Saves both raw valid keys and detailed response logs

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd keytheft

# Install dependencies
pip install -r requirements.txt

# Ensure GitHub CLI is authenticated
gh auth login
```

### Requirements
- Python 3.8+
- GitHub CLI (`gh`) authenticated
- Required packages: `requests`, `rich`, `openai`

## Usage

### Discovering Keys from GitHub

```bash
# Basic search with all shard types
./github_key_search.py --output results/

# Search specific shard types only
./github_key_search.py --shard-types language extension --max-shards 20

# List all available search shards
./github_key_search.py --list-shards

# Customize search parameters
./github_key_search.py --per-page 100 --max-pages-per-shard 10 --delay 2.0
```

#### Search Shard Types
- **Language shards**: Target specific programming languages
- **Extension shards**: Focus on particular file types  
- **Combo shards**: Logical combinations (e.g., Python + .env files)
- **Filename shards**: Search for specific filename patterns
- **Path shards**: Target common configuration directories
- **Basic shard**: Unfiltered search

### Testing Discovered Keys

```bash
# Test all keys from a file
./tester.py --file results/github_keys_sharded_20241221-123456_keys.txt

# Test with custom parameters
./tester.py --file keys.txt --start 10 --limit 50 --delay 2.0

# Test a single key
./tester.py --key "sk-proj-abcd1234..."
```

#### Key Validation Logic
The tester distinguishes between:
- **INVALID**: Authentication failures (401 with "Incorrect API key provided")
- **VALID**: All other responses including:
  - Quota exceeded
  - Rate limited  
  - Billing issues
  - Account suspended
  - Server errors
  - Country restrictions

## Output Files

### GitHub Search Results
- `github_keys_sharded_[timestamp].json` - Complete results with metadata
- `github_keys_sharded_[timestamp]_keys.txt` - Extracted keys only
- `github_keys_sharded_[timestamp]_stats.txt` - Shard performance statistics

### Key Testing Results  
- `valid_keys_[timestamp].txt` - Valid keys only (one per line)
- `valid_keys_detailed_[timestamp].txt` - Valid keys with response details

## Advanced Configuration

### Search Sharding Strategy
The tool uses multiple search dimensions to maximize coverage:

1. **Language-based**: 15+ programming languages
2. **Extension-based**: 17+ file extensions  
3. **Combination**: 20+ logical pairings
4. **Filename**: 8+ common config filenames
5. **Path**: 6+ typical config directories

This approach can theoretically discover up to 37,000+ results (vs GitHub's 1000 limit) by using different query filters that return overlapping but distinct result sets.

### Rate Limiting & Ethics
- Built-in delays between requests (default: 2s)
- Automatic retry logic for rate limit errors
- Respects GitHub's API usage guidelines
- **Educational/Research Use Only**

## Examples

### Typical Workflow
```bash
# 1. Discover keys with focused search
./github_key_search.py --shard-types language extension combo --output discovery/

# 2. Test discovered keys  
./tester.py --file discovery/github_keys_sharded_*_keys.txt --delay 1.5

# 3. Use valid keys for authorized testing/research
```

### High-Yield Search
```bash
# Focus on high-probability locations
./github_key_search.py --shard-types filename path combo --max-shards 25
```

## Legal & Ethical Considerations

**Important**: This tool is for educational and authorized security research purposes only.

- Only test keys you own or have explicit permission to test
- Respect GitHub's Terms of Service and API rate limits
- Follow responsible disclosure for any vulnerabilities found
- Do not use for malicious purposes or unauthorized access

## Troubleshooting

### Common Issues
- **GitHub Auth Errors**: Run `gh auth login` to authenticate
- **Rate Limiting**: Increase `--delay` parameter
- **No Results**: Try different `--shard-types` or check if keys still exist
- **OpenAI Errors**: Ensure `openai` package is updated

### Performance Tips
- Use `--max-shards` to limit search scope for testing
- Increase delays if hitting rate limits frequently
- Focus on high-yield shard types (combo, filename) for efficiency

## Contributing

Contributions welcome! Please ensure any changes maintain the ethical focus and improve the tool's educational value.
