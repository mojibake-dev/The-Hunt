import os
from openai import OpenAI
import time
import argparse

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, TextColumn, BarColumn, TaskProgressColumn

console = Console()

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

def check_api_key(api_key: str) -> tuple[bool, str]:
    """Check whether the provided OpenAI API key is valid by making a small chat completion.

    The function accepts keys with or without a leading "Bearer " prefix.
    Returns (is_valid, response_message) where is_valid is True for any response 
    except authentication errors (401 with invalid key or missing key).
    """
    # Allow passing either the raw key or "Bearer <key>"
    if api_key.lower().startswith("bearer "):
        api_key = api_key.split(" ", 1)[1]

    client = OpenAI(api_key=api_key)
    try:
        resp = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "Say hello!"}],
            max_tokens=5,
        )

        # Extract content from successful response
        content = None
        try:
            content = resp.choices[0].message.content
        except Exception:
            try:
                content = resp.choices[0].message["content"]
            except Exception:
                content = str(resp)

        console.print(f"[green]Key {api_key[:8]}...{api_key[-5:]} is VALID (SUCCESS)[/green]")
        response_message = f"SUCCESS: {content}"
        return True, response_message
        
    except Exception as e:
        # Check the specific exception type and error code for proper categorization
        error_str = str(e)
        
        # Handle OpenAI-specific exceptions by checking error attributes if available
        error_code = None
        error_type = None
        error_message = error_str
        
        # Try to extract error code from the exception
        if hasattr(e, 'status_code'):
            error_code = e.status_code
        elif hasattr(e, 'code'):
            error_code = e.code
        elif "Error code: " in error_str:
            import re
            code_match = re.search(r"Error code: (\d+)", error_str)
            if code_match:
                error_code = int(code_match.group(1))
        
        # Categorize based on HTTP status codes and OpenAI error patterns
        if error_code == 401:
            # 401 errors - check if it's actually an invalid key
            if ("Incorrect API key provided" in error_str or 
                "Invalid API key provided" in error_str or
                "You didn't provide an API key" in error_str):
                console.print(f"[red]Key {api_key[:8]}...{api_key[-5:]} is INVALID (Bad key)[/red]")
                return False, f"INVALID_KEY: {error_str[:200]}"
            else:
                # Other 401 errors might be valid keys with auth issues
                error_type = "Authentication issue"
                
        elif error_code == 400:
            # Bad request - could be model issue, invalid parameters, etc.
            if "model" in error_str.lower() and "does not exist" in error_str.lower():
                error_type = "Model not available"
            elif "maximum context length" in error_str.lower():
                error_type = "Context length exceeded"
            else:
                error_type = "Bad request"
                
        elif error_code == 403:
            # Forbidden - various reasons but key might be valid
            if "country" in error_str.lower() or "region" in error_str.lower():
                error_type = "Country/region not supported"
            elif "organization" in error_str.lower():
                error_type = "Organization access issue"
            elif "billing" in error_str.lower():
                error_type = "Billing required"
            else:
                error_type = "Access forbidden"
                
        elif error_code == 404:
            # Not found - usually model or endpoint issues
            if "model" in error_str.lower():
                error_type = "Model not found"
            else:
                error_type = "Resource not found"
                
        elif error_code == 422:
            # Unprocessable entity - invalid parameters but valid key
            error_type = "Invalid parameters"
            
        elif error_code == 429:
            # Rate limiting or quota issues - key is valid
            if "quota" in error_str.lower() or "insufficient_quota" in error_str.lower():
                error_type = "Quota exceeded"
            elif "rate limit" in error_str.lower():
                error_type = "Rate limited"
            else:
                error_type = "Too many requests"
                
        elif error_code in [500, 502, 503, 504]:
            # Server errors - key is likely valid
            error_type = "Server error"
            
        else:
            # Check for specific error patterns in the message
            error_lower = error_str.lower()
            
            if "quota" in error_lower or "insufficient_quota" in error_lower:
                error_type = "Quota exceeded"
            elif "rate limit" in error_lower:
                error_type = "Rate limited"
            elif "billing" in error_lower:
                error_type = "Billing issue"
            elif "usage limit" in error_lower:
                error_type = "Usage limit reached"
            elif "account" in error_lower and ("deactivat" in error_lower or "suspend" in error_lower):
                error_type = "Account suspended"
            elif "timeout" in error_lower:
                error_type = "Request timeout"
            elif "network" in error_lower or "connection" in error_lower:
                error_type = "Network error"
            else:
                error_type = "Unknown error"
        
        # If we determined an error type, the key is considered valid (just has other issues)
        if error_type:
            console.print(f"[green]Key {api_key[:8]}...{api_key[-5:]} is VALID ({error_type})[/green]")
            response_message = f"VALID_WITH_ERROR: {error_type} - {error_str[:150]}"
            return True, response_message
        else:
            # Fallback for truly unknown errors - assume invalid to be safe
            console.print(f"[red]Key {api_key[:8]}...{api_key[-5:]} is INVALID (Unknown error)[/red]")
            return False, f"INVALID_UNKNOWN: {error_str[:200]}"


def test_keys_from_file(file_path, start_index=0, limit=None, delay=1, output_dir="output/"):
    """
    Test multiple API keys from a file.
    
    Args:
        file_path: Path to the file containing API keys (one per line)
        start_index: Index to start testing from (0-based)
        limit: Maximum number of keys to test
        delay: Delay in seconds between API calls
        output_dir: Directory to save output files
    
    Returns:
        Tuple of (valid_keys_with_responses, total_tested)
    """
    # Check if file exists
    if not os.path.exists(file_path):
        console.print(f"[red]Error: File not found: {file_path}[/red]")
        return [], 0
    
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    # Read all keys from file
    with open(file_path, 'r') as f:
        all_keys = [line.strip() for line in f if line.strip()]
    
    file_info = {
        "File path": file_path,
        "Total keys found": str(len(all_keys)),
        "Output directory": output_dir
    }
    print_info_panel("File Information", file_info)
    
    # Determine which keys to test based on start_index and limit
    end_index = len(all_keys) if limit is None else min(start_index + limit, len(all_keys))
    keys_to_test = all_keys[start_index:end_index]
    
    test_config = {
        "Keys to test": str(len(keys_to_test)),
        "Starting from index": str(start_index),
        "Delay between tests": f"{delay}s"
    }
    print_info_panel("Test Configuration", test_config)
    
    valid_keys_with_responses = []
    
    # Test each key with progress bar
    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console
    ) as progress:
        task = progress.add_task("Testing API keys...", total=len(keys_to_test))
        
        for i, key in enumerate(keys_to_test):
            progress.update(task, description=f"Testing key {start_index + i + 1}/{end_index}")
            
            console.print(f"\n[blue]Testing key: {key[:8]}...{key[-5:]}[/blue]")
            
            is_valid, response = check_api_key(key)
            if is_valid:
                valid_keys_with_responses.append((key, response))
            
            progress.advance(task, 1)
            
            # Add delay between requests to avoid rate limiting
            if i < len(keys_to_test) - 1 and delay > 0:
                time.sleep(delay)
    
    return valid_keys_with_responses, len(keys_to_test)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test OpenAI API keys from a file")
    parser.add_argument("--file", "-f", default="keys.txt", 
                        help="Path to file containing API keys (one per line)")
    parser.add_argument("--start", "-s", type=int, default=0, 
                        help="Start testing from this index (0-based)")
    parser.add_argument("--limit", "-l", type=int, 
                        help="Maximum number of keys to test")
    parser.add_argument("--delay", "-d", type=float, default=1.0, 
                        help="Delay in seconds between API calls")
    parser.add_argument("--key", "-k", 
                        help="Test a single key instead of reading from a file")
    parser.add_argument("--output", "-o", default="output/",
                        help="Output directory for results (default: output/)")
    
    args = parser.parse_args()
    
    print_section("OPENAI API KEY TESTER")
    
    # Check if we're testing a single key
    if args.key:
        single_key_info = {
            "Key to test": f"{args.key[:8]}...{args.key[-5:]}",
            "Mode": "Single key test"
        }
        print_info_panel("Single Key Test", single_key_info)
        
        is_valid, response = check_api_key(args.key)
        
        result_info = {
            "Result": "VALID" if is_valid else "INVALID",
            "Response": response[:100] + "..." if len(response) > 100 else response
        }
        print_info_panel("Test Result", result_info)
        
    else:
        # Test keys from file
        valid_keys_with_responses, total_tested = test_keys_from_file(
            args.file, 
            start_index=args.start, 
            limit=args.limit, 
            delay=args.delay,
            output_dir=args.output
        )
        
        # Report results
        print_section("TEST RESULTS")
        
        results_summary = {
            "Valid keys found": str(len(valid_keys_with_responses)),
            "Total keys tested": str(total_tested),
            "Success rate": f"{(len(valid_keys_with_responses)/total_tested)*100:.1f}%" if total_tested > 0 else "0%"
        }
        print_info_panel("Summary", results_summary)
        
        if valid_keys_with_responses:
            # Create timestamp for files
            timestamp = time.strftime("%Y%m%d-%H%M%S")
            
            # Save valid keys to raw file (one per line)
            valid_keys_file = os.path.join(args.output, f"valid_keys_{timestamp}.txt")
            with open(valid_keys_file, 'w') as f:
                for key, _ in valid_keys_with_responses:
                    f.write(f"{key}\n")
            
            # Save keys with responses to detailed file
            detailed_file = os.path.join(args.output, f"valid_keys_detailed_{timestamp}.txt")
            with open(detailed_file, 'w') as f:
                for key, response in valid_keys_with_responses:
                    f.write(f"Key: {key}\n")
                    f.write(f"Response: {response}\n")
                    f.write("-" * 80 + "\n")
            
            output_files = {
                "Valid keys (raw)": valid_keys_file,
                "Valid keys (detailed)": detailed_file
            }
            print_info_panel("Files Saved", output_files)
            
            console.print("\n[bold]Valid keys found:[/bold]")
            for i, (key, response) in enumerate(valid_keys_with_responses, 1):
                truncated_response = response[:50] + "..." if len(response) > 50 else response
                console.print(f"[green]{i}. {key[:8]}...{key[-5:]}:[/green] {truncated_response}")
        else:
            console.print("[yellow]No valid keys found[/yellow]")
        
        print_section("TEST COMPLETE")
