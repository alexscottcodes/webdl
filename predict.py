import os
import subprocess
import shutil
import re
from pathlib import Path
from typing import Optional
from cog import BasePredictor, Input, Path as CogPath
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.panel import Panel
from rich.text import Text

console = Console()

class Predictor(BasePredictor):
    def predict(
        self,
        url: str = Input(
            description="The URL of the website to scrape (e.g., https://example.com)",
        ),
        max_depth: int = Input(
            description="Maximum depth to crawl (0 = unlimited)",
            default=2,
            ge=0,
            le=10,
        ),
        max_size: int = Input(
            description="Maximum size in MB to download (0 = unlimited)",
            default=100,
            ge=0,
            le=1000,
        ),
        external_links: bool = Input(
            description="Follow links to external domains",
            default=False,
        ),
        include_media: bool = Input(
            description="Download images, videos, and other media files",
            default=True,
        ),
    ) -> CogPath:
        """
        Scrape a website using HTTrack and return a ZIP archive of the results.
        """
        
        # Display startup banner
        console.print(Panel.fit(
            "[bold cyan]🕷️  HTTrack Website Scraper[/bold cyan]\n"
            "[dim]Powered by Replicate Cog[/dim]",
            border_style="cyan"
        ))
        
        # Validate URL
        if not url.startswith(('http://', 'https://')):
            raise ValueError("URL must start with http:// or https://")
        
        # Create output directory
        output_dir = Path("/tmp/httrack_output")
        output_dir.mkdir(exist_ok=True)
        
        # Create project directory
        project_name = "scraped_site"
        project_dir = output_dir / project_name
        
        # Clean up any existing project
        if project_dir.exists():
            shutil.rmtree(project_dir)
        
        # Build HTTrack command
        cmd = [
            "httrack",
            url,
            "-O", str(output_dir),
            f"+{project_name}",
            "-v",  # Verbose mode
            "--quiet=false",
        ]
        
        # Add depth limit
        if max_depth > 0:
            cmd.extend([f"-r{max_depth}"])
        
        # Add size limit
        if max_size > 0:
            cmd.extend([f"-M{max_size}m"])
        
        # External links
        if not external_links:
            cmd.append("-%e0")  # Don't follow external links
        
        # Media handling
        if not include_media:
            cmd.extend([
                "-*gif", "-*jpg", "-*jpeg", "-*png", "-*svg",
                "-*mp4", "-*avi", "-*mov", "-*mp3", "-*wav"
            ])
        
        # Display configuration
        config_text = Text()
        config_text.append("📋 Configuration:\n", style="bold yellow")
        config_text.append(f"  • URL: {url}\n", style="white")
        config_text.append(f"  • Max Depth: {max_depth if max_depth > 0 else 'Unlimited'}\n", style="white")
        config_text.append(f"  • Max Size: {max_size if max_size > 0 else 'Unlimited'} MB\n", style="white")
        config_text.append(f"  • External Links: {'Yes' if external_links else 'No'}\n", style="white")
        config_text.append(f"  • Include Media: {'Yes' if include_media else 'No'}\n", style="white")
        console.print(Panel(config_text, border_style="yellow"))
        
        # Run HTTrack with progress monitoring
        console.print("\n[bold green]🚀 Starting website scrape...[/bold green]\n")
        
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=console,
            ) as progress:
                
                scrape_task = progress.add_task("[cyan]Scraping website...", total=100)
                
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    universal_newlines=True,
                    bufsize=1
                )
                
                files_downloaded = 0
                bytes_downloaded = 0
                
                for line in process.stdout:
                    line = line.strip()
                    
                    # Parse HTTrack output for progress
                    if "File" in line and "downloaded" in line.lower():
                        files_downloaded += 1
                        progress.update(scrape_task, description=f"[cyan]Downloaded {files_downloaded} files...")
                    
                    # Parse bytes/size info
                    size_match = re.search(r'(\d+)\s*bytes?', line, re.IGNORECASE)
                    if size_match:
                        bytes_downloaded += int(size_match.group(1))
                        mb_downloaded = bytes_downloaded / (1024 * 1024)
                        progress.update(
                            scrape_task,
                            description=f"[cyan]Downloaded {files_downloaded} files ({mb_downloaded:.1f} MB)..."
                        )
                    
                    # Check for completion indicators
                    if "mirror complete" in line.lower() or "finished" in line.lower():
                        progress.update(scrape_task, completed=100)
                
                process.wait()
                
                if process.returncode != 0:
                    raise RuntimeError(f"HTTrack failed with return code {process.returncode}")
                
                progress.update(scrape_task, completed=100, description="[green]✓ Scraping complete!")
            
            console.print(f"\n[bold green]✓ Successfully downloaded {files_downloaded} files[/bold green]")
            
            # Create ZIP archive
            console.print("\n[bold yellow]📦 Creating ZIP archive...[/bold yellow]")
            
            zip_path = output_dir / f"{project_name}.zip"
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                zip_task = progress.add_task("[yellow]Compressing files...", total=None)
                
                shutil.make_archive(
                    str(output_dir / project_name),
                    'zip',
                    project_dir
                )
                
                progress.update(zip_task, description="[green]✓ Archive created!")
            
            # Get final stats
            zip_size_mb = zip_path.stat().st_size / (1024 * 1024)
            
            # Display success summary
            summary = Text()
            summary.append("✨ Scraping Complete!\n\n", style="bold green")
            summary.append(f"  📊 Files Downloaded: {files_downloaded}\n", style="white")
            summary.append(f"  💾 Archive Size: {zip_size_mb:.2f} MB\n", style="white")
            summary.append(f"  📦 Output: {zip_path.name}\n", style="white")
            
            console.print(Panel(summary, border_style="green", title="Summary"))
            
            return CogPath(zip_path)
        
        except Exception as e:
            console.print(f"\n[bold red]❌ Error: {str(e)}[/bold red]")
            raise
        
        finally:
            # Clean up the uncompressed directory to save space
            if project_dir.exists():
                shutil.rmtree(project_dir)