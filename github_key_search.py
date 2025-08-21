#!/usr/bin/env python3

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime
from typing import Dict, List

import requests
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeRemainingColumn

console = Console()

def get_github_token() -> str:
    """Get GitHub token from CLI"""
    try:
        result = subprocess.run(['gh', 'auth', 'token'], capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        console.print("[red]Error: Failed to get GitHub token from CLI[/red]")
        console.print("[yellow]Please run 'gh auth login' first[/yellow]")
        sys.exit(1)

def print_section(title: str):
    """Print a section header using rich"""
    console.print(Panel(title, style="bold blue"))

def print_info_panel(title: str, content: dict):
    """Print information in a panel - safely handle all data types"""
    if not content:
        console.print(Panel("No information available", title=title, style="cyan"))
        return
    
    lines = []
    for key, value in content.items():
        # Ensure both key and value are strings
        safe_key = str(key) if key is not None else "Unknown"
        
        if value is None:
            safe_value = "Not specified"
        else:
            safe_value = str(value)
        
        lines.append(f"{safe_key}: {safe_value}")
    
    # Join lines with newlines
    text_content = "\n".join(lines)
    
    try:
        console.print(Panel(text_content, title=title, style="cyan"))
    except Exception as e:
        # Fallback to simple print if Panel fails
        console.print(f"\n=== {title} ===")
        for line in lines:
            console.print(line)
        console.print("=" * (len(title) + 8))

def wait_for_rate_limit_reset(retry_count: int, wait_time: int = 60):
    """Wait for rate limit to reset with rich progress bar"""
    console.print(f"[yellow]Rate limit hit (retry {retry_count}/3)[/yellow]")
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        console=console
    ) as progress:
        task = progress.add_task("Waiting for rate limit reset...", total=wait_time)
        for i in range(wait_time):
            time.sleep(1)
            progress.advance(task, 1)
    
    console.print("[green]Rate limit reset! Continuing...[/green]")

def generate_search_shards() -> List[Dict]:
    """Generate different search query combinations to shard the search"""
    
    # Different programming languages where API keys might be found
    languages = [
        'python', 'javascript', 'typescript', 'java', 'php', 'ruby', 'go', 
        'rust', 'csharp', 'cpp', 'c', 'shell', 'powershell'
    ]
    
    # Common file extensions where API keys are stored
    extensions = [
        'env', 'config', 'ini', 'conf', 'properties', 'settings', 'cfg', 
        'toml', 'yml', 'yaml', 'json', 'txt', 'log', 'py', 'js', 'ts'
    ]
    
    # File type languages (these should be searched separately, not combined)
    file_languages = ['yaml', 'json']
    
    shards = []
    
    # 1. Programming language-based shards
    for lang in languages:
        shards.append({
            'type': 'language',
            'query': f'sk-proj- language:{lang}',
            'description': f'Language: {lang}'
        })
    
    # 2. File type languages (yaml, json) - separate from extensions
    for lang in file_languages:
        shards.append({
            'type': 'language',
            'query': f'sk-proj- language:{lang}',
            'description': f'Language: {lang}'
        })
    
    # 3. File extension shards
    for ext in extensions:
        shards.append({
            'type': 'extension',
            'query': f'sk-proj- extension:{ext}',
            'description': f'Extension: .{ext}'
        })
    
    # 4. Logical combination shards (language + compatible extension)
    logical_combos = [
        # Python files with various extensions
        ('python', 'py'),
        ('python', 'config'),
        ('python', 'ini'),
        
        # JavaScript/TypeScript files
        ('javascript', 'js'),
        ('javascript', 'json'),
        ('javascript', 'config'),
        ('typescript', 'ts'),
        ('typescript', 'json'),
        
        # Shell scripts with config files
        ('shell', 'env'),
        ('shell', 'config'),
        ('shell', 'ini'),
        
        # PowerShell with config
        ('powershell', 'config'),
        ('powershell', 'ini'),
        
        # Java with properties
        ('java', 'properties'),
        ('java', 'config'),
        
        # Configuration file combinations (files that might contain keys in any language)
        ('php', 'config'),
        ('ruby', 'config'),
        ('go', 'config'),
    ]
    
    for lang, ext in logical_combos:
        shards.append({
            'type': 'combo',
            'query': f'sk-proj- language:{lang} extension:{ext}',
            'description': f'Combo: {lang} + .{ext}'
        })
    
    # 5. Configuration-focused shards (files likely to contain API keys)
    config_focused = [
        'sk-proj- filename:.env',
        'sk-proj- filename:config',
        'sk-proj- filename:settings',
        'sk-proj- filename:local',
        'sk-proj- filename:dev',
        'sk-proj- filename:prod',
        'sk-proj- filename:development',
        'sk-proj- filename:production',
    ]
    
    for query in config_focused:
        description = query.replace('sk-proj- filename:', 'Filename contains: ')
        shards.append({
            'type': 'filename',
            'query': query,
            'description': description
        })
    
    # 6. Path-based shards (common locations for API keys)
    path_focused = [
        'sk-proj- path:config',
        'sk-proj- path:env',
        'sk-proj- path:settings',
        'sk-proj- path:.github',
        'sk-proj- path:docker',
        'sk-proj- path:scripts',
    ]
    
    for query in path_focused:
        description = query.replace('sk-proj- path:', 'Path contains: ')
        shards.append({
            'type': 'path',
            'query': query,
            'description': description
        })
    
    # 7. Basic search without filters
    shards.append({
        'type': 'basic',
        'query': 'sk-proj-',
        'description': 'Basic search (no filters)'
    })
    
    return shards

def search_single_shard(token: str, shard: Dict, per_page: int = 100, max_pages: int = 10) -> List[Dict]:
    """Search a single shard with rich formatting"""
    
    # Display shard info
    shard_info = {
        "Description": shard['description'],
        "Query": shard['query']
    }
    print_info_panel("Searching Shard", shard_info)
    
    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/vnd.github.text-match+json'
    }
    
    results = []
    api_key_pattern = re.compile(r'sk-proj-[A-Za-z0-9_-]{40,}')
    
    page = 1
    retry_count = 0
    max_retries = 3
    
    while page <= max_pages:
        params = {
            'q': shard['query'],
            'per_page': per_page,
            'page': page
        }
        
        try:
            response = requests.get('https://api.github.com/search/code', headers=headers, params=params)
            
            if response.status_code == 403:
                retry_count += 1
                if retry_count <= max_retries:
                    console.print(f"[yellow]WARNING: Rate limit hit on page {page} (retry {retry_count}/{max_retries})[/yellow]")
                    wait_for_rate_limit_reset(retry_count)
                    continue  # Retry the same page
                else:
                    console.print(f"[red]ERROR: Max retries ({max_retries}) reached for this shard[/red]")
                    break
            
            # Reset retry count on successful request
            retry_count = 0
            response.raise_for_status()
            data = response.json()
            items = data.get('items', [])
            total_count = data.get('total_count', 0)
            
            if page == 1:
                console.print(f"[blue]Total matches reported: {total_count}[/blue]")
            
            console.print(f"[green]Page {page}: {len(items)} results[/green]")
            
            if len(items) == 0:
                break
            
            # Extract API keys
            page_keys = 0
            for item in items:
                repo_name = item['repository']['full_name']
                file_path = item['path']
                
                text_matches = item.get('text_matches', [])
                for match in text_matches:
                    fragment = match.get('fragment', '')
                    keys = api_key_pattern.findall(fragment)
                    
                    for key in keys:
                        results.append({
                            'key': key,
                            'repository': repo_name,
                            'file_path': file_path,
                            'fragment': fragment,
                            'shard_type': shard['type'],
                            'shard_description': shard['description']
                        })
                        page_keys += 1
            
            if page_keys > 0:
                console.print(f"[cyan]Found {page_keys} API keys on page {page}[/cyan]")
            
            # Only increment page on successful request
            page += 1
            
        except requests.exceptions.RequestException as e:
            if "403" in str(e) or "rate limit" in str(e).lower():
                retry_count += 1
                if retry_count <= max_retries:
                    console.print(f"[yellow]WARNING: Rate limit error on page {page} (retry {retry_count}/{max_retries})[/yellow]")
                    wait_for_rate_limit_reset(retry_count)
                    continue  # Retry the same page
                else:
                    console.print(f"[red]ERROR: Max retries ({max_retries}) reached for this shard[/red]")
                    break
            else:
                error_msg = str(e)[:50]
                console.print(f"[red]ERROR: Error on page {page}: {error_msg}[/red]")
                page += 1  # Skip to next page for non-rate-limit errors
                continue
    
    console.print(f"[green]Shard complete: {len(results)} total API keys found[/green]")
    return results

def search_github_code_sharded(token: str, per_page: int = 100, max_pages_per_shard: int = 10, 
                               shard_types: List[str] = None, max_shards: int = None, 
                               delay_between_shards: float = 2.0) -> List[Dict]:
    """Search with rich progress tracking"""
    
    print_section("STARTING SHARDED SEARCH FOR OPENAI API KEYS")
    
    all_shards = generate_search_shards()
    if shard_types:
        all_shards = [s for s in all_shards if s['type'] in shard_types]
    if max_shards:
        all_shards = all_shards[:max_shards]
    
    config_info = {
        "Total shards": str(len(all_shards)),
        "Max pages per shard": str(max_pages_per_shard),
        "Delay between shards": f"{delay_between_shards}s"
    }
    print_info_panel("Search Configuration", config_info)
    
    all_results = []
    successful_shards = 0
    failed_shards = 0
    
    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console
    ) as progress:
        main_task = progress.add_task("Processing shards...", total=len(all_shards))
        
        for i, shard in enumerate(all_shards, 1):
            progress.update(main_task, description=f"Shard {i}/{len(all_shards)}: {shard['description']}")
            
            try:
                shard_results = search_single_shard(token, shard, per_page, max_pages_per_shard)
                all_results.extend(shard_results)
                successful_shards += 1
                
                if i < len(all_shards) and delay_between_shards > 0:
                    time.sleep(delay_between_shards)
                    
            except KeyboardInterrupt:
                console.print("[red]Interrupted by user[/red]")
                break
            except Exception as e:
                failed_shards += 1
                console.print(f"[red]Shard failed: {str(e)[:50]}[/red]")
                continue
            
            progress.advance(main_task, 1)
    
    # Final results
    results_info = {
        "Successful shards": f"{successful_shards}/{len(all_shards)}",
        "Failed shards": str(failed_shards),
        "Total API keys found": str(len(all_results))
    }
    print_info_panel("Search Complete", results_info)
    
    return all_results

def save_results(results: List[Dict], output_file: str = None):
    """Save results with rich formatting"""
    import os
    
    if not output_file:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output_file = f"github_keys_sharded_{timestamp}.json"
    elif os.path.isdir(output_file):
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output_file = os.path.join(output_file, f"github_keys_sharded_{timestamp}.json")
    
    os.makedirs(os.path.dirname(output_file) if os.path.dirname(output_file) else '.', exist_ok=True)
    
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    keys_file = output_file.replace('.json', '_keys.txt')
    unique_keys = list(set([result['key'] for result in results]))
    
    with open(keys_file, 'w') as f:
        for key in unique_keys:
            f.write(f"{key}\n")
    
    stats_file = output_file.replace('.json', '_stats.txt')
    shard_stats = {}
    for result in results:
        shard_desc = result.get('shard_description', 'unknown')
        shard_stats[shard_desc] = shard_stats.get(shard_desc, 0) + 1
    
    with open(stats_file, 'w') as f:
        f.write("SHARD STATISTICS\n")
        f.write("="*50 + "\n")
        for shard_desc, count in sorted(shard_stats.items(), key=lambda x: x[1], reverse=True):
            f.write(f"{shard_desc}: {count} keys\n")
    
    files_info = {
        "Results file": output_file,
        "Keys file": keys_file,
        "Stats file": stats_file,
        "Total results": str(len(results)),
        "Unique keys": str(len(unique_keys))
    }
    print_info_panel("Files Saved", files_info)

def main():
    parser = argparse.ArgumentParser(description="Search GitHub for OpenAI API keys using sharding")
    parser.add_argument('--per-page', type=int, default=100, dest='per_page', 
                        help='Results per page (default: 100, max: 100)')
    parser.add_argument('--max-pages-per-shard', type=int, default=10, 
                        help='Maximum pages to search per shard (default: 10)')
    parser.add_argument('--shard-types', nargs='+', 
                        choices=['language', 'extension', 'combo', 'filename', 'path', 'basic'],
                        help='Types of shards to search (default: all)')
    parser.add_argument('--max-shards', type=int, 
                        help='Maximum number of shards to search')
    parser.add_argument('--delay', type=float, default=2.0,
                        help='Delay between shards in seconds (default: 2.0)')
    parser.add_argument('--output', help='Output file path')
    parser.add_argument('--list-shards', action='store_true', 
                        help='List all available shards and exit')
    
    args = parser.parse_args()
    
    if args.list_shards:
        shards = generate_search_shards()
        print_section(f"AVAILABLE SHARDS ({len(shards)} total)")
        by_type = {}
        for shard in shards:
            shard_type = shard['type']
            if shard_type not in by_type:
                by_type[shard_type] = []
            by_type[shard_type].append(shard)
        
        for shard_type, type_shards in by_type.items():
            shard_info = {
                "Shard type": str(shard_type).upper(),
                "Total shards": str(len(type_shards))
            }
            
            # Add first few examples
            for i, shard in enumerate(type_shards[:3], 1):
                desc = str(shard.get('description', 'No description'))
                query = str(shard.get('query', 'No query'))
                shard_info[f"Example {i}"] = f"{desc} | Query: {query}"
            
            if len(type_shards) > 3:
                shard_info["Additional"] = f"... and {len(type_shards) - 3} more shards"
            
            print_info_panel(f"{shard_type.upper()} SHARDS", shard_info)
        return
    
    print_section("GITHUB OPENAI API KEY SEARCHER")
    
    console.print("[blue]Getting GitHub token from CLI...[/blue]")
    token = get_github_token()
    
    # Build search parameters dict very carefully
    search_params = {}
    
    # Add basic parameters
    search_params["Per page"] = str(args.per_page)
    search_params["Max pages per shard"] = str(args.max_pages_per_shard)
    search_params["Delay between shards"] = f"{args.delay}s"
    
    # Add optional parameters with safe defaults
    if hasattr(args, 'shard_types') and args.shard_types:
        search_params["Shard types"] = ', '.join(str(t) for t in args.shard_types)
    else:
        search_params["Shard types"] = "All types"
    
    if hasattr(args, 'max_shards') and args.max_shards:
        search_params["Max shards"] = str(args.max_shards)
    else:
        search_params["Max shards"] = "No limit"
    
    if hasattr(args, 'output') and args.output:
        search_params["Output path"] = str(args.output)
    else:
        search_params["Output path"] = "Auto-generated"
    
    # Debug: print the search_params before passing to panel
    console.print(f"[dim]Debug - search_params: {search_params}[/dim]")
    
    print_info_panel("Search Parameters", search_params)
    
    results = search_github_code_sharded(
        token, 
        per_page=args.per_page, 
        max_pages_per_shard=args.max_pages_per_shard,
        shard_types=args.shard_types,
        max_shards=args.max_shards,
        delay_between_shards=args.delay
    )
    
    if results:
        save_results(results, args.output)
        
        # Summary statistics
        unique_keys = set([r['key'] for r in results if 'key' in r])
        unique_repos = set([r['repository'] for r in results if 'repository' in r])
        shard_types_used = set([r['shard_type'] for r in results if 'shard_type' in r])
        
        summary_stats = {
            "Total API key matches": str(len(results)),
            "Unique API keys": str(len(unique_keys)),
            "Unique repositories": str(len(unique_repos)),
            "Shard types used": ', '.join(sorted(str(t) for t in shard_types_used)) if shard_types_used else "None"
        }
        
        print_info_panel("FINAL SUMMARY", summary_stats)
    else:
        print_section("NO RESULTS FOUND")
        console.print("[yellow]No API keys found across all shards[/yellow]")

if __name__ == "__main__":
    main()