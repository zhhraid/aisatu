import { FaceLandmarker, FilesetResolver } from '@mediapipe/tasks-vision';
import { AMBANG_BAWAAN, type Ambang } from './aturan';
import { ambilBlendshape, celahBibir, hitungFitur, posisiWajah } from './fitur';
import { Kalibrasi, type HasilKalibrasi } from './kalibrasi';
import { Percobaan, type HasilPercobaan, type Keadaan, type OpsiPercobaan } from './percobaan';
import { DeteksiSuara, KENDALA_MIKROFON } from './suara';
import type { Blendshape, Bunyi, Fitur, PosisiWajah } from './tipe';

export interface OpsiMata {
  /** Folder berisi berkas WASM MediaPipe (hasil `npm run siapkan`). */
  wasmPath: string;
  /** Lokasi berkas face_landmarker.task. */
  modelPath: string;
  /** Jumlah frame yang diproses per detik. 15 sampai 24 sudah cukup. */
  fps: number;
  ambang: Ambang;
  percobaan: Partial<OpsiPercobaan>;
}

export const OPSI_MATA: OpsiMata = {
  wasmPath: '/wasm',
  modelPath: '/model/face_landmarker.task',
  fps: 20,
  ambang: AMBANG_BAWAAN,
  percobaan: {},
};

export interface FrameMata {
  t: number;
  posisi: PosisiWajah;
  /** null kalau posisi bukan 'ok'. */
  fitur: Fitur | null;
  suara: boolean;
  rms: number;
  /** Ada hembusan napas (desis tanpa nada), untuk "h". */
  napas: boolean;
}

type Pendengar = (frame: FrameMata) => void;

/**
 * Mata: kamera + mikrofon + penilaian, semuanya di perangkat. Video dan suara tidak
 * pernah dikirim ke mana pun; yang keluar dari kelas ini hanya angka dan hasil percobaan.
 *
 * Jangan simpan FrameMata ke state React. Gambar ke canvas lewat ref dari `padaFrame`,
 * dan perbarui state hanya saat ada kejadian.
 */
export class Mata {
  private readonly opsi: OpsiMata;
  private readonly suara = new DeteksiSuara();
  private readonly pendengar = new Set<Pendengar>();
  private video: HTMLVideoElement | null = null;
  private aliran: MediaStream | null = null;
  private netral: Blendshape = {};
  private blendTerakhir: Blendshape | null = null;
  private putaran = 0;
  private tProses = 0;
  private waktuVideo = -1;

  private constructor(
    private readonly penanda: FaceLandmarker,
    opsi: OpsiMata,
  ) {
    this.opsi = opsi;
  }

  /** Memuat model. GPU dicoba dulu, lalu CPU kalau gagal. */
  static async buat(opsi: Partial<OpsiMata> = {}): Promise<Mata> {
    const lengkap = { ...OPSI_MATA, ...opsi };
    const berkas = await FilesetResolver.forVisionTasks(lengkap.wasmPath);
    const buat = (delegate: 'GPU' | 'CPU') =>
      FaceLandmarker.createFromOptions(berkas, {
        baseOptions: { modelAssetPath: lengkap.modelPath, delegate },
        runningMode: 'VIDEO',
        numFaces: 1,
        outputFaceBlendshapes: true,
      });
    let penanda: FaceLandmarker;
    try {
      penanda = await buat('GPU');
    } catch {
      penanda = await buat('CPU');
    }
    return new Mata(penanda, lengkap);
  }

  get ambang(): Ambang {
    return this.opsi.ambang;
  }

  set ambang(baru: Ambang) {
    this.opsi.ambang = baru;
  }

  /** Mengubah opsi percobaan (batas waktu, lama tahan, abaikan suara) untuk percobaan berikutnya. */
  aturPercobaan(opsi: Partial<OpsiPercobaan>): void {
    this.opsi.percobaan = { ...this.opsi.percobaan, ...opsi };
  }

  get terkalibrasi(): boolean {
    return Object.keys(this.netral).length > 0;
  }

  get ambangSuara(): number {
    return this.suara.penentu.ambang;
  }

  /** false kalau izin mikrofon ditolak atau perangkat tidak punya mikrofon. */
  get mikrofonAktif(): boolean {
    return this.suara.aktif;
  }

  /** Meminta izin kamera dan mikrofon, lalu mulai memproses. Panggil dari penangan klik. */
  async mulaiKamera(video: HTMLVideoElement): Promise<void> {
    const kamera = { facingMode: 'user', width: { ideal: 640 }, height: { ideal: 480 } };
    try {
      this.aliran = await navigator.mediaDevices.getUserMedia({
        video: kamera,
        audio: KENDALA_MIKROFON,
      });
    } catch {
      // Mikrofon tidak ada atau ditolak: kamera tetap jalan, suara dianggap tidak ada.
      this.aliran = await navigator.mediaDevices.getUserMedia({ video: kamera });
    }
    video.srcObject = this.aliran;
    video.muted = true;
    video.playsInline = true;
    await video.play();
    this.video = video;
    if (this.aliran.getAudioTracks().length > 0) await this.suara.mulai(this.aliran);
    this.putaran = requestAnimationFrame(this.langkah);
  }

  async berhenti(): Promise<void> {
    cancelAnimationFrame(this.putaran);
    this.aliran?.getTracks().forEach((jalur) => jalur.stop());
    this.aliran = null;
    this.video = null;
    await this.suara.berhenti();
  }

  /** Mendaftarkan pendengar frame. Mengembalikan fungsi untuk berhenti mendengar. */
  padaFrame(pendengar: Pendengar): () => void {
    this.pendengar.add(pendengar);
    return () => this.pendengar.delete(pendengar);
  }

  private readonly langkah = (): void => {
    this.putaran = requestAnimationFrame(this.langkah);
    const video = this.video;
    const kini = performance.now();
    if (!video || video.readyState < 2 || kini - this.tProses < 1000 / this.opsi.fps) return;
    if (video.currentTime === this.waktuVideo) return; // belum ada frame baru
    this.tProses = kini;
    this.waktuVideo = video.currentTime;

    const hasil = this.penanda.detectForVideo(video, kini);
    const titik = hasil.faceLandmarks[0];
    const kategori = hasil.faceBlendshapes[0]?.categories;
    const { ada, rms, napas } = this.suara.adaSuara(kini);

    let posisi: PosisiWajah = 'tidak_ada';
    let fitur: Fitur | null = null;
    this.blendTerakhir = null;
    if (titik && kategori) {
      const lebar = video.videoWidth;
      const tinggi = video.videoHeight;
      posisi = posisiWajah(titik, lebar, tinggi);
      if (posisi === 'ok') {
        this.blendTerakhir = ambilBlendshape(kategori);
        fitur = hitungFitur(this.blendTerakhir, this.netral, celahBibir(titik, lebar, tinggi));
      }
    }
    const frame: FrameMata = { t: kini, posisi, fitur, suara: ada, rms, napas };
    for (const pendengar of this.pendengar) pendengar(frame);
  };

  /**
   * Kalibrasi wajah netral dan kebisingan ruangan (sekitar 2 detik). Anak diam,
   * mulut tertutup. Kalau hasilnya tidak ok, netral lama tetap dipakai.
   */
  async kalibrasi(padaProgres?: (bagian: number) => void): Promise<HasilKalibrasi> {
    const kalibrasi = new Kalibrasi();
    const kebisingan = this.suara.kalibrasi(1000);
    await new Promise<void>((selesai) => {
      const lepas = this.padaFrame((frame) => {
        kalibrasi.tambah(frame.t, frame.posisi === 'ok' ? this.blendTerakhir : null);
        padaProgres?.(kalibrasi.progres());
        if (kalibrasi.selesai()) {
          lepas();
          selesai();
        }
      });
    });
    await kebisingan;
    const hasil = kalibrasi.hasil();
    if (hasil.ok) this.netral = hasil.netral;
    return hasil;
  }

  /**
   * Menjalankan satu percobaan sampai berhasil atau waktu habis.
   * `batal()` menghentikan lebih awal; hasilnya null dan jangan dikirim ke backend.
   */
  percobaan(
    urutan: readonly Bunyi[],
    padaKeadaan?: (keadaan: Keadaan) => void,
  ): { hasil: Promise<HasilPercobaan | null>; batal: () => void } {
    const percobaan = new Percobaan(urutan, this.opsi.ambang, this.opsi.percobaan);
    let batal = (): void => {};
    const hasil = new Promise<HasilPercobaan | null>((selesai) => {
      const lepas = this.padaFrame((frame) => {
        const keadaan = percobaan.proses({ t: frame.t, fitur: frame.fitur, suara: frame.suara, napas: frame.napas });
        padaKeadaan?.(keadaan);
        const akhir = percobaan.hasil();
        if (akhir) {
          lepas();
          selesai(akhir);
        }
      });
      batal = () => {
        lepas();
        selesai(null);
      };
    });
    return { hasil, batal: () => batal() };
  }
}
