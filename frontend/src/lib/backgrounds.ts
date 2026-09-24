const STORAGE_KEY = "rental_os_backgrounds";

const DEFAULTS = [
  "/building_bg.jpg",
  "https://images.unsplash.com/photo-1545324418-cc1a3fa10c00?w=1920&q=80",
  "https://images.unsplash.com/photo-1512917774080-9991f1c4c750?w=1920&q=80",
  "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=1920&q=80",
];

export interface BackgroundConfig {
  urls: string[];
  interval: number;
  opacity: number;
  blur: number;
}

export function getBackgroundConfig(): BackgroundConfig {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (parsed.urls && Array.isArray(parsed.urls) && parsed.urls.length > 0) {
        return {
          urls: parsed.urls,
          interval: parsed.interval ?? 10,
          opacity: parsed.opacity ?? 0.28,
          blur: parsed.blur ?? 16,
        };
      }
    }
  } catch {}
  return { urls: DEFAULTS, interval: 10, opacity: 0.28, blur: 16 };
}

export function saveBackgroundConfig(config: BackgroundConfig) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(config));
}

export function addBackgroundUrl(url: string) {
  const config = getBackgroundConfig();
  if (!config.urls.includes(url)) {
    config.urls.push(url);
    saveBackgroundConfig(config);
  }
  return config;
}

export function removeBackgroundUrl(url: string) {
  const config = getBackgroundConfig();
  config.urls = config.urls.filter((u) => u !== url);
  saveBackgroundConfig(config);
  return config;
}

export function resetBackgrounds() {
  saveBackgroundConfig({ urls: DEFAULTS, interval: 10, opacity: 0.28, blur: 16 });
}
