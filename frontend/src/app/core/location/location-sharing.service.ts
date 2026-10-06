import { DestroyRef, Injectable, inject, signal } from '@angular/core';
import { RealtimeService } from '../ws/realtime.service';

export type SharingStatus = 'off' | 'starting' | 'on' | 'denied' | 'unavailable';

/** Como mucho una posicion cada SEND_MS (el servidor descarta las mas seguidas). */
const SEND_MS = 5000;

interface WakeLockLike {
  release(): Promise<void>;
}

/**
 * Comparte la ubicacion del conductor durante el viaje en curso: sigue el GPS del telefono,
 * envia por el WebSocket como mucho cada 5 s y mantiene la pantalla encendida (Wake Lock)
 * para que el navegador no pause el seguimiento. Al volver a la pestana pide de nuevo el
 * Wake Lock, que el sistema suelta al ocultarla.
 */
@Injectable({ providedIn: 'root' })
export class LocationSharingService {
  private readonly realtime = inject(RealtimeService);

  readonly status = signal<SharingStatus>('off');
  readonly tripId = signal<string | null>(null);
  readonly lastSent = signal<Date | null>(null);
  readonly keepsScreenOn = signal(false);

  private watchId: number | null = null;
  private wakeLock: WakeLockLike | null = null;
  private lastSentAt = 0;

  constructor() {
    const onVisible = () => {
      if (document.visibilityState === 'visible' && this.watchId !== null) {
        void this.holdScreen();
      }
    };
    document.addEventListener('visibilitychange', onVisible);
    inject(DestroyRef).onDestroy(() => {
      document.removeEventListener('visibilitychange', onVisible);
      this.stop();
    });
  }

  start(tripId: string): void {
    if (this.watchId !== null && this.tripId() === tripId) return;
    this.stop();
    const geolocation = globalThis.navigator?.geolocation;
    if (!geolocation) {
      this.status.set('unavailable');
      return;
    }
    this.tripId.set(tripId);
    this.status.set('starting');
    this.watchId = geolocation.watchPosition(
      (position) => this.send(position),
      (error) => {
        this.status.set(error.code === error.PERMISSION_DENIED ? 'denied' : 'unavailable');
        if (error.code === error.PERMISSION_DENIED) this.stop(false);
      },
      { enableHighAccuracy: true, maximumAge: 5000, timeout: 20_000 },
    );
    void this.holdScreen();
  }

  stop(resetStatus = true): void {
    if (this.watchId !== null) globalThis.navigator?.geolocation?.clearWatch(this.watchId);
    this.watchId = null;
    this.tripId.set(null);
    void this.wakeLock?.release().catch(() => undefined);
    this.wakeLock = null;
    this.keepsScreenOn.set(false);
    if (resetStatus) this.status.set('off');
  }

  private send(position: GeolocationPosition): void {
    const tripId = this.tripId();
    const now = Date.now();
    if (!tripId || now - this.lastSentAt < SEND_MS) return;
    const { latitude, longitude, accuracy, heading, speed } = position.coords;
    const sent = this.realtime.send({
      type: 'location.update',
      trip_id: tripId,
      lat: latitude,
      lon: longitude,
      accuracy,
      heading,
      speed,
    });
    if (sent) {
      this.lastSentAt = now;
      this.lastSent.set(new Date(now));
      this.status.set('on');
    }
  }

  private async holdScreen(): Promise<void> {
    const wakeLock = (
      globalThis.navigator as Navigator & {
        wakeLock?: { request(type: 'screen'): Promise<WakeLockLike> };
      }
    )?.wakeLock;
    if (!wakeLock) return;
    try {
      this.wakeLock = await wakeLock.request('screen');
      this.keepsScreenOn.set(true);
    } catch {
      // Sin permiso (por ejemplo, pestana oculta o bateria baja): se sigue sin Wake Lock.
      this.keepsScreenOn.set(false);
    }
  }
}
