// SPDX-License-Identifier: MIT
use serde::{Deserialize, Serialize};
use std::{fmt, fs, path::Path};

#[derive(Clone, Copy, Debug, Default, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "lowercase")]
pub enum Language {
    English,
    #[default]
    Japanese,
}

impl Language {
    pub fn text<T>(self, english: T, japanese: T) -> T {
        match self {
            Self::English => english,
            Self::Japanese => japanese,
        }
    }

    pub fn other(self) -> Self {
        self.text(Self::Japanese, Self::English)
    }

    pub fn load(data: &Path) -> Self {
        fs::read(data.join("launcher-language.json"))
            .ok()
            .and_then(|bytes| serde_json::from_slice(&bytes).ok())
            .unwrap_or_default()
    }

    pub fn save(self, data: &Path) -> crate::Result<()> {
        fs::create_dir_all(data).map_err(|error| error.to_string())?;
        let stage = data.join(format!(".language-{}", crate::unique_suffix()));
        fs::write(&stage, serde_json::to_vec(&self).map_err(|error| error.to_string())?)
            .map_err(|error| error.to_string())?;
        if let Err(error) = fs::rename(&stage, data.join("launcher-language.json")) {
            let _ = fs::remove_file(stage);
            return Err(LaunchError::with_detail(
                "Could not save the display language",
                "表示言語を保存できませんでした",
                error,
            ));
        }
        Ok(())
    }
}

#[derive(Debug)]
pub struct LaunchError {
    english: String,
    japanese: Option<String>,
}

impl LaunchError {
    pub fn new(english: impl Into<String>, japanese: impl Into<String>) -> Self {
        Self {
            english: english.into(),
            japanese: Some(japanese.into()),
        }
    }

    pub fn with_detail(english: &str, japanese: &str, detail: impl fmt::Display) -> Self {
        Self::new(format!("{english}: {detail}"), format!("{japanese}: {detail}"))
    }

    pub fn message(&self, language: Language) -> &str {
        language.text(&self.english, self.japanese.as_ref().unwrap_or(&self.english))
    }
}

impl From<String> for LaunchError {
    fn from(message: String) -> Self {
        Self { english: message, japanese: None }
    }
}
