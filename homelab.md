# Homelab : source de vérité

Ce fichier alimente la section « Homelab » du site (`index.html#homelab`) et du profil GitHub.
Une tâche planifiée le relit chaque jour à 5 h et met à jour les deux si quelque chose a changé.

**Règles :** rien de sensible ici (pas d'IP, de nom de domaine, de nom de machine, de compte, d'identifiant ni de nombre d'entrées). Ce fichier n'est pas servi par le site (`_redirects`).

*Dernière mise à jour : 6 novembre 2026*

## En bref
Homelab sur du matériel de récupération : une tour Windows qui fait tourner 14 conteneurs Docker sous WSL2, et un Raspberry Pi 5 allumé 24 h/24. Accès à distance uniquement par Tailscale, aucun port ouvert sur la box, tous les services en HTTPS.

## Machines
| Machine | Matériel | Système | Services |
|---|---|---|---|
| Tour | Ryzen 5 1600, 16 Go, GTX 1660 Super 6 Go | Windows 10, WSL2, Docker Desktop | Ollama, Open WebUI, Immich, Jellyfin, Navidrome, Home Assistant, n8n, Vaultwarden, Radicale, AdGuard Home, Uptime Kuma, Homepage |
| Raspberry Pi 5 | 8 Go, SSD NVMe 256 Go | Raspberry Pi OS, Docker | Tailscale, AdGuard Home (DNS du réseau, DoH), Vaultwarden, Radicale, Immich |

Préparés mais éteints : Prometheus, Grafana, Paperless-ngx.

## Réseau et sécurité
- Tailscale (WireGuard), MagicDNS, `tailscale serve` comme reverse proxy, certificats Let's Encrypt
- Ports des conteneurs liés à la machine locale uniquement
- Pare-feu sur chaque hôte, activé avec un retour arrière automatique
- SSH par clé, mises à jour de sécurité automatiques
- Secrets dans des fichiers à accès restreint, jamais dans le code
- Sauvegardes versionnées (rsync + dumps des bases) plutôt qu'un RAID

## Problèmes résolus
- Deux machines invisibles sur le VPN : connectées avec deux comptes différents
- Données « perdues » au redémarrage : Docker démarrait avant WSL, script de démarrage qui attend
- Disque de sauvegarde défaillant : diagnostic par les journaux et `chkdsk` en lecture seule
- Migration de services vers le Pi : export des bases, transfert chiffré, SHA256, comparaison des comptages
- IA dans 6 Go de VRAM : modèles 4-8 B, un seul chargé à la fois

## En cours
- Remplacer le disque de sauvegarde et lancer la sauvegarde nocturne

## Prévu
- Ethernet pour la tour et le Pi, puis Wake-on-LAN de la tour depuis le Pi
- ACL Tailscale écrites à la main
- Réactiver Prometheus et Grafana
- Labo Kubernetes (k3s)
