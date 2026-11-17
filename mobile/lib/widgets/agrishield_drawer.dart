import 'package:material_ui/material_ui.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../core/strings.dart';
import '../core/theme.dart';
import '../providers.dart';
import 'agrishield_logo.dart';

/// One drawer shared by the shell screens; the logo is the header.
class AgriDrawer extends ConsumerWidget {
  const AgriDrawer({super.key});

  void _go(BuildContext context, String route) {
    Navigator.of(context).pop();
    context.go(route);
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final lang = ref.watch(appProvider.select((s) => s.language));

    return Drawer(
      child: ListView(
        padding: EdgeInsets.zero,
        children: [
          Container(
            color: AgriBrand.navy,
            padding: const EdgeInsets.fromLTRB(20, 48, 20, 24),
            child: const Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                AgriShieldLogo(
                  width: 58,
                  height: 58,
                  showWordmark: true,
                  wordmarkColor: Colors.white,
                ),
                SizedBox(height: 10),
                Text(
                  'Smart Farming. Healthy Crops.',
                  style: TextStyle(fontSize: 14, color: Colors.white70),
                ),
              ],
            ),
          ),
          ListTile(
            leading: const Icon(Icons.home_rounded, size: 28),
            title: Text(L.t(lang, 'navHome')),
            onTap: () => _go(context, '/home'),
          ),
          ListTile(
            leading: const Icon(Icons.photo_camera_rounded, size: 28),
            title: Text(L.t(lang, 'checkCrop')),
            onTap: () {
              Navigator.of(context).pop();
              context.push('/camera');
            },
          ),
          ListTile(
            leading: const Icon(Icons.history_rounded, size: 28),
            title: Text(L.t(lang, 'historyTitle')),
            onTap: () => _go(context, '/history'),
          ),
          const Divider(),
          ListTile(
            leading: const Icon(Icons.info_outline_rounded, size: 28),
            title: const Text('About AgriShield'),
            onTap: () => _go(context, '/about'),
          ),
          ListTile(
            leading: const Icon(Icons.person_rounded, size: 28),
            title: Text(L.t(lang, 'profileTitle')),
            onTap: () => _go(context, '/profile'),
          ),
          ListTile(
            leading: const Icon(Icons.support_agent_rounded, size: 28),
            title: Text(L.t(lang, 'helpTitle')),
            onTap: () => _go(context, '/help'),
          ),
        ],
      ),
    );
  }
}
