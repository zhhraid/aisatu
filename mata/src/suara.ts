/** Kenyaringan (RMS) dari satu potong sinyal suara. */
export function hitungRms(sampel: Float32Array): number {
  if (sampel.length === 0) return 0;
  let jumlah = 0;
  for (const v of sampel) jumlah += v * v;
  return Math.sqrt(jumlah / sampel.length);
}

export interface OpsiSuara {
  /** Suara dianggap ada kalau kenyaringan melebihi kebisingan ruangan dikali ini. */
  faktor: number;
  /** Ambang terendah, supaya ruangan yang sangat sunyi tidak membuat napas terhitung suara. */
  ambangMin: number;
  /** Suara dianggap masih ada selama ini setelah kenyaringan turun, supaya tidak berkedip. */
  tahanMs: number;
}

export const OPSI_SUARA: OpsiSuara = { faktor: 2.5, ambangMin: 0.015, tahanMs: 150 };

/** Memutuskan ada suara atau tidak dari nilai kenyaringan. Tanpa Web Audio, jadi bisa diuji. */
export class PenentuSuara {
  private kebisingan = 0;
  private terakhirAda = -Infinity;

  constructor(private readonly opsi: OpsiSuara = OPSI_SUARA) {}

  aturKebisingan(rms: number): void {
    this.kebisingan = rms;
  }

  get ambang(): number {
    return Math.max(this.kebisingan * this.opsi.faktor, this.opsi.ambangMin);
  }

  perbarui(rms: number, t: number): boolean {
    if (rms > this.ambang) this.terakhirAda = t;
    return t - this.terakhirAda <= this.opsi.tahanMs;
  }
}

/** Mikrofon lewat Web Audio API. */
export class DeteksiSuara {
  private konteks: AudioContext | null = null;
  private analis: AnalyserNode | null = null;
  private penyangga: Float32Array<ArrayBuffer> | null = null;
  readonly penentu: PenentuSuara;

  constructor(opsi: OpsiSuara = OPSI_SUARA) {
    this.penentu = new PenentuSuara(opsi);
  }

  /** Panggil dari penangan klik, karena browser mewajibkan gestur pengguna untuk audio. */
  async mulai(aliran: MediaStream): Promise<void> {
    this.konteks = new AudioContext();
    await this.konteks.resume();
    this.analis = this.konteks.createAnalyser();
    this.analis.fftSize = 1024;
    this.penyangga = new Float32Array(this.analis.fftSize);
    this.konteks.createMediaStreamSource(aliran).connect(this.analis);
  }

  get aktif(): boolean {
    return this.analis !== null;
  }

  rms(): number {
    if (!this.analis || !this.penyangga) return 0;
    this.analis.getFloatTimeDomainData(this.penyangga);
    return hitungRms(this.penyangga);
  }

  /** Mengukur kebisingan ruangan. Minta anak diam selama pengukuran. */
  async kalibrasi(durasiMs = 1000): Promise<number> {
    const nilai: number[] = [];
    const mulai = performance.now();
    while (performance.now() - mulai < durasiMs) {
      nilai.push(this.rms());
      await new Promise((selesai) => setTimeout(selesai, 50));
    }
    const rata = nilai.reduce((a, b) => a + b, 0) / Math.max(nilai.length, 1);
    this.penentu.aturKebisingan(rata);
    return rata;
  }

  adaSuara(t: number): { ada: boolean; rms: number } {
    const rms = this.rms();
    return { ada: this.penentu.perbarui(rms, t), rms };
  }

  async berhenti(): Promise<void> {
    await this.konteks?.close();
    this.konteks = null;
    this.analis = null;
  }
}

/** Pengaturan mikrofon: pengolah otomatis dimatikan karena mengacaukan ambang kenyaringan. */
export const KENDALA_MIKROFON: MediaTrackConstraints = {
  echoCancellation: false,
  noiseSuppression: false,
  autoGainControl: false,
};
