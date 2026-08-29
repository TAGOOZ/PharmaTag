mod printing;

#[tauri::command]
fn greet(name: &str) -> String {
    format!("Hello, {}!", name)
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_sql::Builder::default().build())
        .invoke_handler(tauri::generate_handler![
            greet,
            printing::list_printers,
            printing::print_raw,
            printing::open_drawer,
            printing::print_label
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}