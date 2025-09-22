export class BufferOptimized {
    private buffer: Buffer[] = [];
    length: number = 0;
    readonly byteLength: number;

    constructor(byteLength: number) {
        this.byteLength = byteLength;
    }

    push(data: Buffer): void {
        if (!data || data.length === 0) return;
        this.buffer.push(data);
        this.length += data.length;
    }

    readBytes(): Buffer | null {
        if (this.length < this.byteLength) {
            return null;
        }

        const result = Buffer.allocUnsafe(this.byteLength);
        let offset = 0;

        while (offset < this.byteLength && this.buffer.length > 0) {
            const chunk = this.buffer[0];
            const need = this.byteLength - offset;

            if (chunk.length <= need) {
                chunk.copy(result, offset);
                offset += chunk.length;
                this.buffer.shift();
            } else {
                chunk.copy(result, offset, 0, need);
                this.buffer[0] = chunk.slice(need);
                offset += need;
            }
        }

        this.length -= this.byteLength;
        return result;
    }
}


/* export class BufferOptimized{
    private buffer: Array<Buffer> = [];
    length: number = 0;
    byteLength: number = 0;
    constructor(byteLength: number) {
        this.byteLength = byteLength;
    }
    push(data: Buffer){
        this.buffer.push(data);
        this.length += data.byteLength;
    }
    readBytes(){
        let buffer = Buffer.alloc(this.byteLength);
        let chunkSize = 0;
        this.buffer.find((chunk, i) => {
            if (chunkSize === 0) {
                chunk.copy(buffer, 0, 0, this.byteLength);
                chunkSize = Math.min(chunk.length, this.byteLength);
                this.buffer[i] = chunk.slice(this.byteLength);
            } else {
                let req = this.byteLength - chunkSize;
                let tmpChunk: Buffer;
                tmpChunk = req < chunk.length ? chunk.slice(0, req) : chunk;
                tmpChunk.copy(buffer, chunkSize);
                chunkSize += tmpChunk.length;
                this.buffer[i] = chunk.slice(req);
            }
            return chunkSize >= this.byteLength;
        });
        this.length -= this.byteLength;
        this.buffer.splice(
            0,
            this.buffer.findIndex(i => i.length),
        );
        return buffer;
    }
} */
