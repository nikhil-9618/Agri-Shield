import 'package:material_ui/material_ui.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/strings.dart';
import '../core/theme.dart';
import '../models/models.dart';
import '../providers.dart';
import '../widgets/common.dart';

class ProfileScreen extends ConsumerStatefulWidget {
  const ProfileScreen({super.key});

  @override
  ConsumerState<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends ConsumerState<ProfileScreen> {
  late final TextEditingController _name;
  late final TextEditingController _village;
  late final TextEditingController _server;
  late String _language;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    final settings = ref.read(appProvider).settings;
    _name = TextEditingController(text: settings.user?.name == 'Farmer' ? '' : settings.user?.name);
    _village = TextEditingController(text: settings.user?.village ?? '');
    _server = TextEditingController(text: settings.serverUrl);
    _language = settings.language;
  }

  @override
  void dispose() {
    _name.dispose();
    _village.dispose();
    _server.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    setState(() => _saving = true);
    final notifier = ref.read(appProvider.notifier);
    await notifier.setServerUrl(_server.text);
    await notifier.saveProfile(
      name: _name.text,
      village: _village.text,
      language: _language,
    );
    if (!mounted) return;
    setState(() => _saving = false);
    showBigSnack(context, L.t(_language, 'savedToast'));
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(appProvider);
    final lang = state.language;
    final phone = state.settings.user?.phone ?? '';

    return Scaffold(
      appBar: AppBar(
        title: Text(L.t(lang, 'profileTitle')),
        actions: [
          SpeakerButton(
            text: '${L.t(lang, 'profileTitle')}. ${L.t(lang, 'languageLabel')}',
            language: lang,
            color: Colors.white,
          ),
          const SizedBox(width: 6),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Row(
                children: [
                  const CircleAvatar(
                    radius: 34,
                    backgroundColor: AgriColors.secondarySoft,
                    child: Icon(Icons.person_rounded, size: 40, color: AgriColors.primary),
                  ),
                  const SizedBox(width: 14),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          state.farmerName.isEmpty
                              ? L.t(lang, 'greetFarmer')
                              : state.farmerName,
                          style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w800),
                        ),
                        Text(
                          phone.isEmpty
                              ? L.t(lang, 'helpPrivacy')
                              : '${'•' * 6}${phone.length > 4 ? phone.substring(phone.length - 4) : ''}',
                          style: const TextStyle(fontSize: 16, color: AgriColors.inkSoft),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 18),
          TextField(
            controller: _name,
            textInputAction: TextInputAction.next,
            style: const TextStyle(fontSize: 21),
            decoration: InputDecoration(
              labelText: L.t(lang, 'nameLabel'),
              prefixIcon: const Icon(Icons.badge_rounded),
              border: const OutlineInputBorder(),
            ),
          ),
          const SizedBox(height: 14),
          TextField(
            controller: _village,
            style: const TextStyle(fontSize: 21),
            decoration: InputDecoration(
              labelText: L.t(lang, 'villageLabel'),
              prefixIcon: const Icon(Icons.location_city_rounded),
              border: const OutlineInputBorder(),
            ),
          ),
          const SizedBox(height: 22),
          Text(
            L.t(lang, 'languageLabel'),
            style: const TextStyle(fontSize: 21, fontWeight: FontWeight.w800),
          ),
          const SizedBox(height: 10),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: kLanguages.map((code) {
              final selected = code == _language;
              return ChoiceChip(
                label: Text(L.languageNames[code] ?? code),
                selected: selected,
                onSelected: (_) {
                  setState(() => _language = code);
                  ref.read(appProvider.notifier).setLanguage(code);
                },
              );
            }).toList(),
          ),
          const SizedBox(height: 22),
          TextField(
            controller: _server,
            keyboardType: TextInputType.url,
            autocorrect: false,
            style: const TextStyle(fontSize: 18),
            decoration: InputDecoration(
              labelText: L.t(lang, 'serverLabel'),
              prefixIcon: const Icon(Icons.dns_rounded),
              border: const OutlineInputBorder(),
            ),
          ),
          const SizedBox(height: 8),
          Text(
            L.t(lang, 'localDisclaimer'),
            style: const TextStyle(fontSize: 15, color: AgriColors.inkSoft),
          ),
          const SizedBox(height: 20),
          FilledButton.icon(
            onPressed: _saving ? null : _save,
            icon: _saving
                ? const SizedBox(
                    width: 24,
                    height: 24,
                    child: CircularProgressIndicator(color: Colors.white, strokeWidth: 3),
                  )
                : const Icon(Icons.save_rounded, size: 28),
            label: Text(L.t(lang, 'saveButton')),
          ),
        ],
      ),
    );
  }
}
