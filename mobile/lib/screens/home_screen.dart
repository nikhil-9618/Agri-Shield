import 'package:material_ui/material_ui.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../core/strings.dart';
import '../core/theme.dart';
import '../providers.dart';
import '../widgets/common.dart';

class HomeScreen extends ConsumerStatefulWidget {
  const HomeScreen({super.key});

  @override
  ConsumerState<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends ConsumerState<HomeScreen> {
  bool _syncing = false;

  @override
  void initState() {
    super.initState();
    Future.microtask(_startup);
  }

  Future<void> _startup() async {
    await ref.read(appProvider.notifier).ensureAccount();
    if (!mounted) return;
    if (ref.read(appProvider).queue.isNotEmpty) {
      await _sync(showToast: false);
    }
  }

  Future<void> _sync({bool showToast = true}) async {
    if (_syncing) return;
    setState(() => _syncing = true);
    final lang = ref.read(appProvider).language;
    final count = await ref.read(appProvider.notifier).syncQueue();
    if (!mounted) return;
    setState(() => _syncing = false);
    if (!showToast) return;
    if (count > 0) {
      showBigSnack(context, L.t(lang, 'syncedCount', vars: {'count': '$count'}));
    } else {
      showBigSnack(context, L.t(lang, 'serverOffline'));
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(appProvider);
    final lang = state.language;
    final greeting = state.farmerName.isEmpty
        ? L.t(lang, 'greetFarmer')
        : L.t(lang, 'greet', vars: {'name': state.farmerName});
    final greetingSpeech = '$greeting ${L.t(lang, 'homeQuestion')}';

    return Scaffold(
      backgroundColor: AgriColors.background,
      body: CustomScrollView(
        slivers: [
          SliverToBoxAdapter(
            child: Container(
              padding: const EdgeInsets.fromLTRB(20, 18, 14, 22),
              decoration: const BoxDecoration(
                color: AgriColors.primary,
                borderRadius: BorderRadius.only(
                  bottomLeft: Radius.circular(30),
                  bottomRight: Radius.circular(30),
                ),
              ),
              child: Row(
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          greeting,
                          style: const TextStyle(
                            fontSize: 30,
                            fontWeight: FontWeight.w900,
                            color: Colors.white,
                          ),
                        ),
                        const SizedBox(height: 6),
                        Text(
                          L.t(lang, 'homeQuestion'),
                          style: const TextStyle(fontSize: 19, color: Colors.white70),
                        ),
                      ],
                    ),
                  ),
                  SpeakerButton(text: greetingSpeech, language: lang, color: Colors.white),
                ],
              ),
            ),
          ),
          if (state.queue.isNotEmpty)
            SliverToBoxAdapter(
              child: OfflineBanner(
                pending: state.queue.length,
                language: lang,
                onSync: () => _sync(),
                syncing: _syncing,
              ),
            ),
          SliverPadding(
            padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
            sliver: SliverList.separated(
              itemCount: 4,
              separatorBuilder: (_, _) => const SizedBox(height: 14),
              itemBuilder: (context, i) {
                if (i == 0) {
                  return ActionTile(
                    icon: Icons.photo_camera_rounded,
                    title: L.t(lang, 'checkCrop'),
                    subtitle: L.t(lang, 'checkCropSub'),
                    color: AgriColors.primary,
                    speakText: L.t(lang, 'checkCrop'),
                    onTap: () => context.push('/camera'),
                  );
                }
                if (i == 1) {
                  return ActionTile(
                    icon: Icons.cloud_rounded,
                    title: L.t(lang, 'weatherAction'),
                    subtitle: L.t(lang, 'weatherActionSub'),
                    color: const Color(0xFF1565C0),
                    speakText: L.t(lang, 'weatherAction'),
                    onTap: () => context.go('/weather'),
                  );
                }
                if (i == 2) {
                  return ActionTile(
                    icon: Icons.history_rounded,
                    title: L.t(lang, 'myProblems'),
                    subtitle: state.saved.isEmpty
                        ? L.t(lang, 'historyEmptyBody')
                        : '${state.saved.length} • ${state.saved.first.diseaseName}',
                    color: AgriColors.warning,
                    speakText: L.t(lang, 'myProblems'),
                    onTap: () => context.push('/history'),
                  );
                }
                return ActionTile(
                  icon: Icons.support_agent_rounded,
                  title: L.t(lang, 'getHelp'),
                  subtitle: L.t(lang, 'getHelpSub'),
                  color: AgriColors.urgent,
                  speakText: L.t(lang, 'getHelp'),
                  onTap: () => context.go('/help'),
                );
              },
            ),
          ),
          SliverToBoxAdapter(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(18, 6, 18, 24),
              child: Row(
                children: [
                  IconButton(
                    onPressed: () => context.push('/alerts'),
                    iconSize: 30,
                    tooltip: L.t(lang, 'alertsTitle'),
                    icon: const Icon(Icons.notifications_rounded, color: AgriColors.inkSoft),
                  ),
                  const Spacer(),
                  IconButton(
                    onPressed: () => context.push('/profile'),
                    iconSize: 30,
                    tooltip: L.t(lang, 'profileTitle'),
                    icon: const Icon(Icons.person_rounded, color: AgriColors.inkSoft),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
