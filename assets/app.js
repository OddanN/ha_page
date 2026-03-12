const dataUrl = "data/site.generated.json";

const titleNode = document.querySelector("#site-title");
const descriptionNode = document.querySelector("#site-description");
const profileLinkNode = document.querySelector("#profile-link");
const sourceLinkNode = document.querySelector("#source-link");
const chipsNode = document.querySelector("#filter-chips");
const featuredSectionNode = document.querySelector("#featured-section");
const featuredStatCardNode = document.querySelector("#featured-stat-card");
const featuredGridNode = document.querySelector("#featured-grid");
const repoGridNode = document.querySelector("#repo-grid");
const totalNode = document.querySelector("#stat-total");
const featuredNode = document.querySelector("#stat-featured");
const updatedNode = document.querySelector("#stat-updated");
const acknowledgementsNode = document.querySelector("#acknowledgements-text");
const acknowledgementsSpecialNode = document.querySelector("#acknowledgements-special");
const acknowledgementsListNode = document.querySelector("#acknowledgements-list");
const template = document.querySelector("#repo-card-template");

const numberFormatter = new Intl.NumberFormat("ru-RU");
const dateFormatter = new Intl.DateTimeFormat("ru-RU", {
  dateStyle: "medium",
  timeStyle: "short",
});

async function main() {
  try {
    const response = await fetch(dataUrl, { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const payload = await response.json();
    renderSite(payload);
  } catch (error) {
    renderError(error);
  }
}

function renderSite(payload) {
  const { site = {}, collection = {}, generated_at: generatedAt, repos = [] } = payload;
  const featuredRepos = repos.filter((repo) => repo.featured);
  const regularRepos = repos.filter((repo) => !repo.featured);

  document.title = site.title || "GitHub Pages";
  titleNode.textContent = site.title || "Коллекция репозиториев";
  renderDescription(site);
  acknowledgementsNode.textContent =
    site.acknowledgements ||
    "Спасибо всем, кто тестирует интеграции, присылает багрепорты, предлагает идеи и помогает доводить проекты до рабочего состояния.";
  renderAcknowledgements(site.special_thanks || []);

  if (site.github_profile_url) {
    profileLinkNode.href = site.github_profile_url;
  }

  if (site.source_repository_url) {
    sourceLinkNode.href = site.source_repository_url;
  }

  totalNode.textContent = numberFormatter.format(repos.length);
  featuredNode.textContent = numberFormatter.format(featuredRepos.length);
  updatedNode.textContent = generatedAt ? dateFormatter.format(new Date(generatedAt)) : "нет данных";

  renderChips(collection.filters || []);
  featuredStatCardNode.classList.toggle("hidden", featuredRepos.length === 0);
  featuredSectionNode.classList.toggle("hidden", featuredRepos.length === 0);
  renderRepoList(featuredGridNode, featuredRepos, "Избранные репозитории пока не выбраны.");
  renderRepoList(repoGridNode, regularRepos, "Подходящие репозитории пока не найдены. Проверьте фильтры в site.config.json.");
}

function renderDescription(site) {
  descriptionNode.replaceChildren();
  const description = site.description || "";
  const linkLabel = site.description_link_label;
  const linkUrl = site.description_link_url;

  if (!linkLabel || !linkUrl) {
    descriptionNode.textContent = description;
    return;
  }

  if (description) {
    descriptionNode.append(document.createTextNode(`${description} `));
  }

  const linkNode = document.createElement("a");
  linkNode.className = "hero-inline-link";
  linkNode.href = linkUrl;
  linkNode.target = "_blank";
  linkNode.rel = "noreferrer";
  linkNode.textContent = linkLabel;
  descriptionNode.append(linkNode);
}

function renderChips(filters) {
  chipsNode.replaceChildren();

  if (!filters.length) {
    chipsNode.append(createTextNode("Фильтры не настроены"));
    return;
  }

  filters.forEach((filterLabel) => {
    const chip = document.createElement("span");
    chip.className = "chip";
    chip.textContent = filterLabel;
    chipsNode.append(chip);
  });
}

function renderRepoList(targetNode, repos, emptyMessage) {
  targetNode.replaceChildren();

  if (!repos.length) {
    targetNode.append(createTextNode(emptyMessage));
    return;
  }

  repos.forEach((repo) => targetNode.append(createRepoCard(repo)));
}

function renderAcknowledgements(entries) {
  acknowledgementsListNode.replaceChildren();
  acknowledgementsSpecialNode.classList.toggle("hidden", entries.length === 0);

  entries.forEach((entry) => {
    const item = document.createElement("div");
    item.className = "acknowledgement-chip";

    const nameNode = document.createElement(entry.url ? "a" : "span");
    nameNode.className = "acknowledgement-name";
    nameNode.textContent = entry.label || entry.name || "Unknown";

    if (entry.url) {
      nameNode.href = entry.url;
      nameNode.target = "_blank";
      nameNode.rel = "noreferrer";
    }

    item.append(nameNode);

    if (entry.note) {
      const noteNode = document.createElement("span");
      noteNode.className = "acknowledgement-note";
      noteNode.textContent = entry.note;
      item.append(noteNode);
    }

    acknowledgementsListNode.append(item);
  });
}

function createRepoCard(repo) {
  const fragment = template.content.cloneNode(true);
  const badgesNode = fragment.querySelector(".repo-badges");
  const nameNode = fragment.querySelector(".repo-name");
  const readmeBadgesNode = fragment.querySelector(".repo-readme-badges");
  const descriptionNode = fragment.querySelector(".repo-description");
  const metaNode = fragment.querySelector(".repo-meta");
  const topicsNode = fragment.querySelector(".repo-topics");
  const releaseLinkNode = fragment.querySelector(".repo-release-link");
  const logoSlotNode = fragment.querySelector(".repo-logo-slot");

  const badges = [];
  if (repo.featured) {
    badges.push("featured");
  }
  if (repo.archived) {
    badges.push("archived");
  }
  if (repo.fork) {
    badges.push("fork");
  }

  if (badges.length) {
    badgesNode.textContent = badges.join(" • ");
  } else {
    badgesNode.remove();
  }
  nameNode.textContent = repo.name;
  nameNode.href = repo.html_url;
  renderReadmeBadges(readmeBadgesNode, repo.readme_badges || []);
  descriptionNode.textContent = repo.description || "Описание не заполнено.";

  const metaItems = [
    { label: "Язык", value: repo.language || "не указан" },
    { label: "Звёзды", value: numberFormatter.format(repo.stargazers_count || 0) },
  ];

  if (repo.release_badge) {
    const badgeImage = document.createElement("img");
    badgeImage.className = "repo-release-badge";
    badgeImage.src = repo.release_badge.image_url;
    badgeImage.alt = repo.release_badge.alt || "release badge";
    badgeImage.loading = "lazy";

    releaseLinkNode.href = repo.release_badge.link_url || repo.latest_release?.html_url || repo.html_url;
    releaseLinkNode.replaceChildren(badgeImage);
    releaseLinkNode.classList.add("has-badge");
    releaseLinkNode.classList.remove("hidden");
  } else if (repo.latest_release) {
    metaItems.push({
      label: "Релиз",
      value: `${repo.latest_release.tag_name} (${formatDate(repo.latest_release.published_at)})`,
    });
    releaseLinkNode.href = repo.latest_release.html_url;
    releaseLinkNode.textContent = repo.latest_release.tag_name;
    releaseLinkNode.classList.remove("has-badge");
    releaseLinkNode.classList.remove("hidden");
  } else {
    releaseLinkNode.classList.remove("has-badge");
  }

  metaItems.forEach(({ label, value }) => {
    const item = document.createElement("div");
    item.className = "repo-meta-pill";
    const labelNode = document.createElement("span");
    labelNode.className = "repo-meta-label";
    labelNode.textContent = `${label}:`;
    const valueNode = document.createElement("span");
    valueNode.className = "repo-meta-value";
    valueNode.textContent = value;
    item.append(labelNode, valueNode);
    metaNode.append(item);
  });

  (repo.topics || []).slice(0, 5).forEach((topic) => {
    const pill = document.createElement("span");
    pill.className = "topic-pill";
    pill.textContent = topic;
    topicsNode.append(pill);
  });

  if (repo.logo_url) {
    const logoNode = document.createElement("img");
    logoNode.className = "repo-logo";
    logoNode.src = repo.logo_url;
    logoNode.alt = `${repo.name} logo`;
    logoSlotNode.replaceChildren(logoNode);
    logoSlotNode.classList.remove("hidden");
  }

  return fragment;
}

function renderReadmeBadges(targetNode, badges) {
  targetNode.replaceChildren();

  if (!badges.length) {
    targetNode.remove();
    return;
  }

  badges.slice(0, 4).forEach((badge) => {
    const badgeImage = document.createElement("img");
    badgeImage.className = "repo-readme-badge";
    badgeImage.src = badge.image_url;
    badgeImage.alt = badge.alt || "";
    badgeImage.loading = "lazy";

    if (badge.link_url) {
      const linkNode = document.createElement("a");
      linkNode.href = badge.link_url;
      linkNode.target = "_blank";
      linkNode.rel = "noreferrer";
      linkNode.append(badgeImage);
      targetNode.append(linkNode);
      return;
    }

    targetNode.append(badgeImage);
  });
}

function createTextNode(message) {
  const node = document.createElement("div");
  node.className = "empty-state";
  node.textContent = message;
  return node;
}

function formatDate(value) {
  if (!value) {
    return "нет данных";
  }

  return dateFormatter.format(new Date(value));
}

function renderError(error) {
  const message = `Не удалось загрузить данные: ${error.message}`;
  renderChips([]);
  renderRepoList(featuredGridNode, [], message);
  renderRepoList(repoGridNode, [], "После первого запуска GitHub Actions здесь появится каталог репозиториев.");
}

main();
