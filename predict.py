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
        if output_dir.exists():
            shutil.rmtree(output_dir)
        output_dir.mkdir(exist_ok=True)
        
        # Create project directory - HTTrack will create subdirectories
        project_name = "website_scrape"
        
        # Build HTTrack command
        cmd = [
            "httrack",
            url,
            "-O", str(output_dir / project_name),
            "-v",  # Verbose mode
            "--display",
        ]
        
        # Add depth limit
        if max_depth > 0:
            cmd.extend([f"-r{max_depth}"])
        else:
            cmd.extend(["-r9"])  # HTTrack max depth
        
        # Add size limit
        if max_size > 0:
            cmd.extend([f"-M{max_size * 1048576}"])  # Convert MB to bytes
        
        # External links
        if not external_links:
            cmd.extend(["-%e0"])  # Don't follow external links
        
        # Media handling
        if not include_media:
            cmd.extend([
                "-*gif", "-*jpg", "-*jpeg", "-*png", "-*svg", "-*webp",
                "-*mp4", "-*avi", "-*mov", "-*mp3", "-*wav", "-*ico"
            ])
        
        # Additional options for better results
        cmd.extend([
            "--quiet",  # Less verbose
            "-c8",  # Max simultaneous connections
            "-%v",  # No verbose mode (cleaner output)
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
                last_progress = 0
                
                for line in process.stdout:
                    line = line.strip()
                    
                    if not line:
                        continue
                    
                    # Parse HTTrack progress percentage
                    percent_match = re.search(r'(\d+)%', line)
                    if percent_match:
                        percent = int(percent_match.group(1))
                        if percent > last_progress:
                            last_progress = percent
                            progress.update(scrape_task, completed=percent)
                    
                    # Count files
                    if re.search(r'File generated|saved|written', line, re.IGNORECASE):
                        files_downloaded += 1
                        progress.update(
                            scrape_task,
                            description=f"[cyan]Downloaded {files_downloaded} files..."
                        )
                    
                    # Parse bytes transferred
                    bytes_match = re.search(r'(\d+)\s*bytes?\s+transferred', line, re.IGNORECASE)
                    if bytes_match:
                        bytes_downloaded = int(bytes_match.group(1))
                        mb_downloaded = bytes_downloaded / (1024 * 1024)
                        progress.update(
                            scrape_task,
                            description=f"[cyan]Downloading... ({mb_downloaded:.1f} MB)"
                        )
                
                process.wait()
                
                if process.returncode != 0:
                    console.print(f"[yellow]⚠ HTTrack exited with code {process.returncode}[/yellow]")
                
                progress.update(scrape_task, completed=100, description="[green]✓ Scraping complete!")
            
            # Find the actual scraped content
            project_dir = output_dir / project_name
            
            if not project_dir.exists():
                raise RuntimeError(f"HTTrack did not create expected directory: {project_dir}")
            
            # Count files in the scraped directory
            all_files = list(project_dir.rglob("*"))
            file_count = sum(1 for f in all_files if f.is_file())
            
            # Calculate total size
            total_size = sum(f.stat().st_size for f in all_files if f.is_file())
            total_size_mb = total_size / (1024 * 1024)
            
            console.print(f"\n[bold green]✓ Successfully scraped {file_count} files ({total_size_mb:.2f} MB)[/bold green]")
            
            # Debug: Show directory structure
            console.print(f"[dim]Output directory: {project_dir}[/dim]")
            subdirs = [d.name for d in project_dir.iterdir() if d.is_dir()]
            if subdirs:
                console.print(f"[dim]Subdirectories: {', '.join(subdirs[:5])}{'...' if len(subdirs) > 5 else ''}[/dim]")
            
            # Create ZIP archive
            console.print("\n[bold yellow]📦 Creating ZIP archive...[/bold yellow]")
            
            zip_path = output_dir / "scraped_website.zip"
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                zip_task = progress.add_task("[yellow]Compressing files...", total=None)
                
                # Create archive from the project directory
                shutil.make_archive(
                    str(output_dir / "scraped_website"),
                    'zip',
                    project_dir
                )
                
                progress.update(zip_task, description="[green]✓ Archive created!")
            
            # Verify ZIP was created
            if not zip_path.exists():
                raise RuntimeError(f"ZIP file was not created at {zip_path}")
            
            # Get final stats
            zip_size_mb = zip_path.stat().st_size / (1024 * 1024)
            
            # Display success summary
            summary = Text()
            summary.append("✨ Scraping Complete!\n\n", style="bold green")
            summary.append(f"  📊 Files Scraped: {file_count}\n", style="white")
            summary.append(f"  💾 Total Size: {total_size_mb:.2f} MB\n", style="white")
            summary.append(f"  📦 Archive Size: {zip_size_mb:.2f} MB\n", style="white")
            summary.append(f"  📁 Output: {zip_path.name}\n", style="white")
            
            console.print(Panel(summary, border_style="green", title="Summary"))
            
            return CogPath(zip_path)
        
        except Exception as e:
            console.print(f"\n[bold red]❌ Error: {str(e)}[/bold red]")
            
            # Debug info
            if output_dir.exists():
                console.print(f"\n[yellow]Debug Info:[/yellow]")
                console.print(f"Output dir exists: {output_dir.exists()}")
                if output_dir.exists():
                    contents = list(output_dir.rglob("*"))
                    console.print(f"Contents found: {len(contents)} items")
                    for item in contents[:10]:  # Show first 10 items
                        console.print(f"  - {item.relative_to(output_dir)}")
            
            raise