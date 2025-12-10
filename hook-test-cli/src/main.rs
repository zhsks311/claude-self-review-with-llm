use clap::{Parser, Subcommand};
use colored::*;
use serde::{Deserialize, Serialize};
use std::io::Write;
use std::process::{Command, Stdio};
use std::time::Instant;

#[derive(Parser)]
#[command(name = "hook-test")]
#[command(about = "Hook system test CLI - Evaluate Claude Code self-review effectiveness")]
#[command(version)]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// Run a benchmark test on the hook system
    Bench {
        /// Number of iterations
        #[arg(short, long, default_value = "10")]
        iterations: u32,
        /// Actually invoke the Python hook (requires Python)
        #[arg(long)]
        real: bool,
    },
    /// Simulate a tool call to trigger hooks
    Simulate {
        /// Tool name (Edit, Write, Bash, TodoWrite)
        #[arg(short, long)]
        tool: String,
        /// File path for Edit/Write tools
        #[arg(short, long)]
        file: Option<String>,
    },
    /// Actually invoke the Python hook with test data
    Invoke {
        /// Stage (plan, code, test, final)
        #[arg(short, long, default_value = "code")]
        stage: String,
        /// Code content to review
        #[arg(short, long)]
        code: Option<String>,
        /// File path
        #[arg(short, long)]
        file: Option<String>,
    },
    /// Show hook system status
    Status,
    /// Generate a test file with intentional issues
    Generate {
        /// Type of issue (bug, security, style)
        #[arg(short, long, default_value = "bug")]
        issue_type: String,
    },
}

#[derive(Serialize, Deserialize, Debug)]
struct HookInput {
    session_id: String,
    tool_name: String,
    tool_input: serde_json::Value,
    cwd: String,
}

#[derive(Serialize, Deserialize, Debug)]
struct HookOutput {
    #[serde(rename = "continue")]
    should_continue: bool,
    #[serde(rename = "systemMessage")]
    system_message: Option<String>,
}

fn main() {
    let cli = Cli::parse();

    match cli.command {
        Commands::Bench { iterations, real } => run_benchmark(iterations, real),
        Commands::Simulate { tool, file } => run_simulation(&tool, file),
        Commands::Invoke { stage, code, file } => invoke_hook(&stage, code, file),
        Commands::Status => show_status(),
        Commands::Generate { issue_type } => generate_test_file(&issue_type),
    }
}

fn run_benchmark(iterations: u32, real: bool) {
    println!("{}", "=== Hook System Benchmark ===".cyan().bold());
    println!("Running {} iterations (real: {})...\n", iterations, real);

    let start = Instant::now();
    let mut timings: Vec<std::time::Duration> = Vec::new();

    for i in 1..=iterations {
        let iter_start = Instant::now();

        if real {
            // Actually call the Python hook
            let result = call_python_hook("code", &serde_json::json!({
                "session_id": format!("bench-{}", i),
                "tool_name": "Edit",
                "tool_input": {
                    "file_path": "bench_test.rs",
                    "old_string": "fn old() {}",
                    "new_string": "fn new() {}"
                },
                "cwd": std::env::current_dir().unwrap().to_string_lossy().to_string()
            }));

            match result {
                Ok(_) => print!("{}", ".".green()),
                Err(_) => print!("{}", "x".red()),
            }
        } else {
            // Simulate hook call delay
            std::thread::sleep(std::time::Duration::from_millis(50));
            print!("{}", ".".green());
        }

        let elapsed = iter_start.elapsed();
        timings.push(elapsed);
    }
    println!();

    let total = start.elapsed();
    let avg = total / iterations;

    // Calculate stats
    let min = timings.iter().min().unwrap();
    let max = timings.iter().max().unwrap();

    println!("\n{}", "Results:".green().bold());
    println!("  Total time: {:?}", total);
    println!("  Average: {:?}", avg);
    println!("  Min: {:?}", min);
    println!("  Max: {:?}", max);
    if avg.as_millis() > 0 {
        println!("  Throughput: {:.2} calls/sec", 1000.0 / avg.as_millis() as f64);
    }
}

fn run_simulation(tool: &str, file: Option<String>) {
    println!("{}", format!("=== Simulating {} Tool ===", tool).cyan().bold());

    let hook_input = HookInput {
        session_id: format!("test-{}", chrono::Utc::now().timestamp()),
        tool_name: tool.to_string(),
        tool_input: match tool {
            "Edit" => serde_json::json!({
                "file_path": file.unwrap_or_else(|| "test.rs".to_string()),
                "old_string": "fn old() {}",
                "new_string": "fn new() { /* TODO: implement */ }"
            }),
            "Write" => serde_json::json!({
                "file_path": file.unwrap_or_else(|| "test.rs".to_string()),
                "content": "fn main() {\n    println!(\"test\");\n}"
            }),
            "TodoWrite" => serde_json::json!({
                "todos": [
                    {"content": "Implement feature", "status": "pending"},
                    {"content": "Write tests", "status": "pending"}
                ]
            }),
            _ => serde_json::json!({}),
        },
        cwd: std::env::current_dir()
            .map(|p| p.to_string_lossy().to_string())
            .unwrap_or_else(|_| ".".to_string()),
    };

    println!("\n{}", "Hook Input:".yellow());
    println!("{}", serde_json::to_string_pretty(&hook_input).unwrap());

    // Simulate hook response
    let response = HookOutput {
        should_continue: true,
        system_message: Some("[자기검열-code] ✅ 검토 통과".to_string()),
    };

    println!("\n{}", "Expected Hook Output:".yellow());
    println!("{}", serde_json::to_string_pretty(&response).unwrap());
}

fn show_status() {
    println!("{}", "=== Hook System Status ===".cyan().bold());

    // Check if config exists
    let config_path = std::path::Path::new("config.json");
    let plugin_path = std::path::Path::new("plugin.json");

    println!("\n{}", "Configuration Files:".yellow());
    println!("  config.json: {}", if config_path.exists() { "✅ Found".green() } else { "❌ Missing".red() });
    println!("  plugin.json: {}", if plugin_path.exists() { "✅ Found".green() } else { "❌ Missing".red() });

    if config_path.exists() {
        if let Ok(content) = std::fs::read_to_string(config_path) {
            if let Ok(config) = serde_json::from_str::<serde_json::Value>(&content) {
                println!("\n{}", "Enabled Adapters:".yellow());
                if let Some(adapters) = config.get("enabled_adapters").and_then(|a| a.as_array()) {
                    for adapter in adapters {
                        println!("  - {}", adapter.as_str().unwrap_or("unknown").green());
                    }
                }
            }
        }
    }
}

fn generate_test_file(issue_type: &str) {
    println!("{}", format!("=== Generating Test File ({}) ===", issue_type).cyan().bold());

    let content = match issue_type {
        "bug" => r#"// Test file with intentional bug
fn calculate_average(numbers: &[i32]) -> i32 {
    let sum: i32 = numbers.iter().sum();
    sum / numbers.len() as i32  // BUG: Division by zero if empty
}

fn main() {
    let empty: Vec<i32> = vec![];
    println!("Average: {}", calculate_average(&empty));
}
"#,
        "security" => r#"// Test file with security issue
use std::process::Command;

fn run_user_command(input: &str) {
    // SECURITY: Command injection vulnerability
    Command::new("sh")
        .arg("-c")
        .arg(input)  // Unsanitized user input!
        .spawn()
        .expect("Failed to execute");
}

fn main() {
    run_user_command("echo hello; rm -rf /");
}
"#,
        "style" => r#"// Test file with style issues
fn BadFunctionName() {  // Should be snake_case
    let X = 5;  // Should be lowercase
    let unused_var = 10;  // Unused variable
    println!("{}",X);  // Missing space
}
"#,
        _ => "// Unknown issue type\nfn main() {}\n",
    };

    let filename = format!("test_{}.rs", issue_type);
    std::fs::write(&filename, content).expect("Failed to write file");

    println!("\n{} {}", "Created:".green(), filename);
    println!("\n{}", "File Content:".yellow());
    println!("{}", content);
    println!("\n{}", "Now use 'hook-test simulate -t Edit -f <file>' to test the hook".cyan());
}

fn invoke_hook(stage: &str, code: Option<String>, file: Option<String>) {
    println!("{}", format!("=== Invoking Hook (stage: {}) ===", stage).cyan().bold());

    let code_content = if let Some(c) = code {
        c
    } else if let Some(f) = &file {
        std::fs::read_to_string(f).unwrap_or_else(|_| "// Could not read file".to_string())
    } else {
        "fn example() { /* test code */ }".to_string()
    };

    let hook_input = serde_json::json!({
        "session_id": format!("invoke-{}", chrono::Utc::now().timestamp()),
        "tool_name": "Edit",
        "tool_input": {
            "file_path": file.unwrap_or_else(|| "test.rs".to_string()),
            "old_string": "",
            "new_string": code_content
        },
        "cwd": std::env::current_dir().unwrap().to_string_lossy().to_string()
    });

    println!("\n{}", "Sending to Python hook...".yellow());
    let start = Instant::now();

    match call_python_hook(stage, &hook_input) {
        Ok(output) => {
            let elapsed = start.elapsed();
            println!("\n{} ({:?})", "Hook Response:".green().bold(), elapsed);

            if let Ok(parsed) = serde_json::from_str::<HookOutput>(&output) {
                let status = if parsed.should_continue {
                    "✅ CONTINUE".green()
                } else {
                    "❌ BLOCKED".red()
                };
                println!("  Decision: {}", status);

                if let Some(msg) = parsed.system_message {
                    println!("\n{}", "System Message:".yellow());
                    for line in msg.lines() {
                        println!("  {}", line);
                    }
                }
            } else {
                println!("  Raw output: {}", output);
            }
        }
        Err(e) => {
            println!("\n{} {}", "Error:".red().bold(), e);
        }
    }
}

fn call_python_hook(stage: &str, input: &serde_json::Value) -> Result<String, String> {
    let wrapper_input = serde_json::json!({
        "stage": stage,
        "hook_input": input
    });

    let mut child = Command::new("python")
        .arg("review_orchestrator.py")
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| format!("Failed to start Python: {}", e))?;

    if let Some(mut stdin) = child.stdin.take() {
        stdin
            .write_all(wrapper_input.to_string().as_bytes())
            .map_err(|e| format!("Failed to write to stdin: {}", e))?;
    }

    let output = child
        .wait_with_output()
        .map_err(|e| format!("Failed to wait for process: {}", e))?;

    if output.status.success() {
        Ok(String::from_utf8_lossy(&output.stdout).to_string())
    } else {
        let stderr = String::from_utf8_lossy(&output.stderr);
        Err(format!("Hook failed: {}", stderr))
    }
}
