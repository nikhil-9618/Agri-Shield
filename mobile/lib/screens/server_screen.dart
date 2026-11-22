import 'package:material_ui/material_ui.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/api_client.dart';
import '../core/strings.dart';
import '../core/theme.dart';
import '../models/models.dart';
import '../providers.dart';
import '../widgets/common.dart';

/// Lets a farmer (or the helper setting up the phone) point the app at a
/// self-hosted AgriShield backend. Weather, the assistant and the cloud
/// fallback need one; on-device leaf diagnosis works without it.
class ServerScreen extends ConsumerStatefulWidget {
  const ServerScreen({super.key});

  @override
  ConsumerState<ServerScreen> createState() => _ServerScreenState();
}

class _ServerScreenState extends ConsumerState<ServerScreen> {
  late final TextEditingController _url;
  bool _testing = false;
  bool _saving = false;
  String? _messageKey;
  bool _messageOk = false;

  @override
  void initState() {
    super.initState();
    _url = TextEditingController(text: ref.read(appProvider).settings.serverUrl);
  }

  @override
  void dispose() {
    _url.dispose();
    super.dispose();
  }

  Future<void> _test() async {
    final url = normalizeServerUrl(_url.text);
    if (url == null) {
      setState(() {
        _messageKey = 'serverTestFail';
        _messageOk = false;
      });
      return;
    }
    setState(() {
      _testing = true;
      _messageKey = null;
    });
    final ok = await ApiClient(baseUrl: url, tokenProvider: () => null).health();
    if (!mounted) return;
    setState(() {
      _testing = false;
      _messageKey = ok ? 'serverTestOk' : 'serverTestFail';
      _messageOk = ok;
    });
  }

  Future<void> _save() async {
    final notifier = ref.read(appProvider.notifier);
    setState(() => _saving = true);
    final error = await notifier.setServerUrl(_url.text);
    if (!mounted) return;
    if (error != null) {
      setState(() {
        _saving = false;
        _messageKey = 'serverTestFail';
        _messageOk = false;
      });
      return;
    }
    _url.text = ref.read(appProvider).settings.serverUrl;
    // Sign in silently on the new server so weather and the assistant work
    // straight away when the address is reachable.
    await notifier.ensureAccount();
    if (!mounted) return;
    ref.invalidate(connectionProvider);
    setState(() => _saving = false);
    showBigSnack(context, L.t(ref.read(appProvider).language, 'savedToast'));
  }

  @override
  Widget build(BuildContext context) {
    final lang = ref.watch(appProvider.select((s) => s.language));
    final saved = ref.watch(appProvider.select((s) => s.settings.serverUrl));
    final connection = ref.watch(connectionProvider);

    return Scaffold(
      appBar: AppBar(
        title: Text(L.t(lang, 'serverTitle')),
        actions: [
          SpeakerButton(
            text: '${L.t(lang, 'serverTitle')}. ${L.t(lang, 'serverIntro')}',
            language: lang,
            color: Colors.white,
          ),
          const SizedBox(width: 6),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text(
            L.t(lang, 'serverIntro'),
            style: const TextStyle(fontSize: 19),
          ),
          const SizedBox(height: 16),
          Card(
            child: ListTile(
              leading: Icon(
                saved.isEmpty ? Icons.cloud_off_rounded : Icons.dns_rounded,
                color: saved.isEmpty ? AgriColors.warning : AgriColors.primary,
                size: 32,
              ),
              title: Text(
                saved.isEmpty ? L.t(lang, 'serverNotSet') : saved,
                style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700),
              ),
              subtitle: connection.when(
                data: (ok) => Text(
                  L.t(lang, ok ? 'onlineMode' : 'offlineMode'),
                  style: const TextStyle(fontSize: 16),
                ),
                loading: () => const Text('...'),
                error: (_, _) => Text(L.t(lang, 'offlineMode')),
              ),
              trailing: connection.isLoading
                  ? const SizedBox(
                      width: 24,
                      height: 24,
                      child: CircularProgressIndicator(strokeWidth: 3),
                    )
                  : null,
            ),
          ),
          const SizedBox(height: 18),
          TextField(
            controller: _url,
            keyboardType: TextInputType.url,
            autocorrect: false,
            enableSuggestions: false,
            style: const TextStyle(fontSize: 19),
            decoration: InputDecoration(
              labelText: L.t(lang, 'serverLabel'),
              hintText: L.t(lang, 'serverUrlHint'),
              helperText: L.t(lang, 'serverUrlHint'),
              helperMaxLines: 2,
              prefixIcon: const Icon(Icons.link_rounded),
              border: const OutlineInputBorder(),
            ),
          ),
          const SizedBox(height: 14),
          Row(
            children: [
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: _testing || _saving ? null : _test,
                  icon: _testing
                      ? const SizedBox(
                          width: 22,
                          height: 22,
                          child: CircularProgressIndicator(strokeWidth: 3),
                        )
                      : const Icon(Icons.wifi_tethering_rounded),
                  label: Text(L.t(lang, 'serverTestButton')),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: FilledButton.icon(
                  onPressed: _saving || _testing ? null : _save,
                  icon: _saving
                      ? const SizedBox(
                          width: 22,
                          height: 22,
                          child: CircularProgressIndicator(
                            color: Colors.white,
                            strokeWidth: 3,
                          ),
                        )
                      : const Icon(Icons.check_rounded),
                  label: Text(L.t(lang, 'serverSaveButton')),
                ),
              ),
            ],
          ),
          if (_messageKey != null) ...[
            const SizedBox(height: 16),
            Container(
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: _messageOk ? AgriColors.secondarySoft : AgriColors.warningSoft,
                borderRadius: BorderRadius.circular(16),
              ),
              child: Row(
                children: [
                  Icon(
                    _messageOk ? Icons.check_circle_rounded : Icons.error_outline_rounded,
                    color: _messageOk ? AgriColors.primary : AgriColors.warning,
                    size: 30,
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      L.t(lang, _messageKey!),
                      style: const TextStyle(fontSize: 18),
                    ),
                  ),
                ],
              ),
            ),
          ],
          const SizedBox(height: 18),
          Text(
            L.t(lang, 'localDisclaimer'),
            style: const TextStyle(fontSize: 15, color: AgriColors.inkSoft),
          ),
        ],
      ),
    );
  }
}
