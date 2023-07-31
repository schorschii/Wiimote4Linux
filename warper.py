#!/usr/bin/env python3
# *-* coding: utf-8 *-*

class warper:
	srcX = [0, 1, 0, 1]
	srcY = [0, 0, 1, 1]
	dstX = [0, 1, 0, 1]
	dstY = [0, 0, 1, 1]
	srcMat  = [0] * 16
	dstMat  = [0] * 16
	warpMat = [0] * 16
	computed = False

	def setSource(self, x0, y0, x1, y1, x2, y2, x3, y3):
		self.srcX[0] = x0
		self.srcY[0] = y0
		self.srcX[1] = x1
		self.srcY[1] = y1
		self.srcX[2] = x2
		self.srcY[2] = y2
		self.srcX[3] = x3
		self.srcY[3] = y3
		self.computed = False

	def setDestination(self, x0, y0, x1, y1, x2, y2, x3, y3):
		self.dstX[0] = x0
		self.dstY[0] = y0
		self.dstX[1] = x1
		self.dstY[1] = y1
		self.dstX[2] = x2
		self.dstY[2] = y2
		self.dstX[3] = x3
		self.dstY[3] = y3
		self.computed = False

	def computeWarp(self):
		self.srcMat = self.computeQuadToSquare(
			self.srcX[0], self.srcY[0],
			self.srcX[1], self.srcY[1],
			self.srcX[2], self.srcY[2],
			self.srcX[3], self.srcY[3]
		)
		self.dstMat = self.computeSquareToQuad(
			self.dstX[0], self.dstY[0],
			self.dstX[1], self.dstY[1],
			self.dstX[2], self.dstY[2],
			self.dstX[3], self.dstY[3]
		)
		self.multMats()
		self.computed = True

	def multMats(self):
		for r in range(0, 4):
			ri = r * 4
			for c in range(0, 4):
				self.warpMat[ri + c] = (
					self.srcMat[ri] * self.dstMat[c]
					+ self.srcMat[ri + 1] * self.dstMat[c + 4]
					+ self.srcMat[ri + 2] * self.dstMat[c + 8]
					+ self.srcMat[ri + 3] * self.dstMat[c + 12]
				)

	def computeSquareToQuad(self, x0, y0, x1, y1, x2, y2, x3, y3):
		dx1 = x1 - x2; dy1 = y1 - y2
		dx2 = x3 - x2; dy2 = y3 - y2
		sx = x0 - x1 + x2 - x3
		sy = y0 - y1 + y2 - y3
		g = (sx * dy2 - dx2 * sy) / (dx1 * dy2 - dx2 * dy1)
		h = (dx1 * sy - sx * dy1) / (dx1 * dy2 - dx2 * dy1)
		a = x1 - x0 + g * x1
		b = x3 - x0 + h * x3
		c = x0
		d = y1 - y0 + g * y1
		e = y3 - y0 + h * y3
		f = y0

		mat = [0] * 16
		mat[0] = a
		mat[1] = d
		mat[2] = 0
		mat[3] = g
		mat[4] = b
		mat[5] = e
		mat[6] = 0
		mat[7] = h
		mat[8] = 0
		mat[9] = 0
		mat[10] = 1
		mat[11] = 0
		mat[12] = c
		mat[13] = f
		mat[14] = 0
		mat[15] = 1
		return mat

	def computeQuadToSquare(self, x0, y0, x1, y1, x2, y2, x3, y3):
		mat = self.computeSquareToQuad(x0, y0, x1, y1, x2, y2, x3, y3)
		# invert through adjoint

		# ignore
		a__1 = mat[0]; d__2 = mat[1]; g__3 = mat[3]
		# 3rd col
		b__4 = mat[4]; e__5 = mat[5]; h__6 = mat[7]
		# ignore 3rd row

		c__7 = mat[12]; f__8 = mat[13]

		A__9 = e__5 - f__8 * h__6
		B__10 = c__7 * h__6 - b__4
		C__11 = b__4 * f__8 - c__7 * e__5
		D__12 = f__8 * g__3 - d__2
		E__13 = a__1 - c__7 * g__3
		F__14 = c__7 * d__2 - a__1 * f__8
		G__15 = d__2 * h__6 - e__5 * g__3
		H__16 = b__4 * g__3 - a__1 * h__6
		I = a__1 * e__5 - b__4 * d__2

		# Probably unnecessary since 'I' is also scaled by the determinant,
		#   and 'I' scales the homogeneous coordinate, which, in turn,
		#   scales the X,Y coordinates.
		# Determinant  =   a * (e - f * h) + b * (f * g - d) + c * (d * h - e * g);
		idet = 1.0 / (a__1 * A__9 + b__4 * D__12 + c__7 * G__15)

		mat[0] = A__9 * idet
		mat[1] = D__12 * idet
		mat[2] = 0
		mat[3] = G__15 * idet
		mat[4] = B__10 * idet
		mat[5] = E__13 * idet
		mat[6] = 0
		mat[7] = H__16 * idet
		mat[8] = 0
		mat[9] = 0
		mat[10] = 1
		mat[11] = 0
		mat[12] = C__11 * idet
		mat[13] = F__14 * idet
		mat[14] = 0
		mat[15] = I * idet
		return mat

	def warp(self, srcX, srcY):
		if not self.computed: self.computeWarp()
		return self._warp(self.warpMat, srcX, srcY)

	def _warp(self, mat, srcX, srcY):
		result = [0] * 4
		z = 0
		result[0] = (srcX * mat[0] + srcY * mat[4] + z * mat[8] + 1 * mat[12])
		result[1] = (srcX * mat[1] + srcY * mat[5] + z * mat[9] + 1 * mat[13])
		result[2] = (srcX * mat[2] + srcY * mat[6] + z * mat[10] + 1 * mat[14])
		result[3] = (srcX * mat[3] + srcY * mat[7] + z * mat[11] + 1 * mat[15])
		return result[0] / result[3], result[1] / result[3]
